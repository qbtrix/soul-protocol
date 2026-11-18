# pi-soul-engine — third-party implementation note

> Status: informational. This is a self-assessment by the implementer, not a conformance certification. Nothing here changes the spec.

`pi-soul-engine` is a TypeScript runtime that embeds Soul Protocol inside the [pi](https://github.com/badlogic/pi-mono) coding agent. It exposes the protocol to the agent as tools and slash commands, injects soul context into the prompt, binds a soul per agent, and persists through a detached worker process so that saves do not block the host. It is a port of the reference runtime's behaviour (memory tiers, psychology pipeline, DNA, evolution, trust chain), not a binding to the Python package. The implementation is private; no repository URL is provided. This note exists because [SPEC.md §11](../SPEC.md) anticipates implementations in other languages, and it records (1) where we stand against §11, honestly, and (2) a few mechanisms we built that the reference implementation might find useful.

Statements about the reference implementation below were checked against `docs/SPEC.md`, `docs/memory-architecture.md`, `docs/trust-chain.md`, `docs/org-journal-spec.md` and `src/soul_protocol/` at `dev`. Statements about our implementation were checked against our source and tests.

## Conformance against SPEC §11 (0.4.0 required boxes)

| §11 requirement | Status | Reason |
|---|---|---|
| Read/write `.soul` at schema_version 0.4.0, flat and nested memory layouts | PARTIAL | We read and write a flat layout of `memory/<name>.json` files (our codec follows format version 1.0.0 of the soul-file spec, `manifest.json` + `soul.json` + `memory/*.json`). The nested `memory/<layer>/<domain>/entries.jsonl` layout is not read: files we do not recognise are listed in an import report as ignored. We also do not write `.jsonl`. |
| Open-string layers and `domain` namespacing (§4.1, §4.2) | PARTIAL | The layer map is open: unknown `memory/<layer>.json` files that look like entry lists are adopted as custom layers. `domain` and `user_id` are stored. But our `MemoryEntry.type` union is closed (`core`, `episodic`, `semantic`, `procedural`), recall's domain filter lets entries with a null domain through every domain filter, and there is no write-side domain enforcement. |
| Round-trip 0.3.x into 0.4.0 form | PARTIAL | Import is tolerant and reports what it normalised. Absent `user_id` and `domain` stay null; they are not mapped to `None`/`"default"` as §11 states for `domain`. Only a hand-built fixture has been exercised, never a `.soul` exported by the Python reference. |
| `Journal.append` / `Journal.query` with `action_prefix` (§8) | NOT IMPLEMENTED | We have a per-session observation journal for crash recovery (see mechanism 2). It is not the §8 journal: no `EventEntry`, no `seq`/`prev_hash`, no `query(action_prefix=...)`. |
| Emit scope-non-empty `EventEntry` records with UTC timestamps (§8) | NOT IMPLEMENTED | No `EventEntry` records are emitted. |
| Round-trip reference-produced `.soul` without field loss (§2) | PARTIAL | Graph edge lists are folded into our entity model and custom layers are folded into the layer map, each with an import report; the original shapes are not preserved on re-export. |
| Implement `CognitiveEngine` (§10) | PARTIAL | Our engine interface is `think(prompt, opts?) -> Promise<string>`: string in, string out like §10, with an optional options argument and an async return. Behind it sits a tiered router with a heuristic fallback, a circuit breaker, a cache and a budget. We have not run it against any shared conformance test. |

## 0.5.0 additive primitives and the optional trust chain

| Item | Status | Reason |
|---|---|---|
| Round-trip `retrieval_weight`, `supersedes`, `prediction_error` | NOT IMPLEMENTED | None of the three fields exist in our `MemoryEntry`. We have `superseded_by` only. |
| `min_weight` filter on `recall()` (default 0.1) | NOT IMPLEMENTED | Our recall accepts an optional `min_activation`, which defaults to no floor. It is not `retrieval_weight`. |
| Memory verbs and PE bands | NOT IMPLEMENTED | We expose supersede (via conflicting facts at observe time) and `forget`, which hard-deletes. No `confirm`, `update`, `purge` or `reinstate`, and no prediction-error bands. |
| Trust chain: read, write, verify (§10A) | PRESENT, NOT CONFORMANT | SHA-256 hash chain over `seq`/`timestamp`/`action`/`payload`/`prev_hash`, with an Ed25519 signature over the hash bytes. Differences from §10A: payloads are stored as a string and, for new entries, carry a sha256 of user text instead of raw text, rather than a `payload_hash` field over canonical JSON; the genesis `prev_hash` is the string `"genesis"`, not 64 zeros; one chain-level public key instead of a per-entry `public_key` and `actor_did`; the hash input is a newline-joined string, not canonical JSON; no timestamp-skew check; no key rotation; no entry cap and no `chain.pruned`. |
| Bind verification to the keystore public key (§10A.7) | NOT IMPLEMENTED | Verification uses the chain's own public key only. We therefore do not claim "verifiable history" in the §10A.7 sense; at most "self-consistent chain". |
| Generate Ed25519 keypairs and sign entries | IMPLEMENTED | Via `node:crypto`. |

## Conformance claim

We claim **no full 0.4.0 conformance** today. The gaps are: the §8 journal and `EventEntry` semantics; the nested memory layout on read; the closed memory-type union; write-side domain enforcement; the trust-chain wire format; and the 0.5.0 memory-update primitives. We would not describe the implementation as "0.4.0 (no trust chain)" either, because the journal boxes are open.

## Mechanisms we built that may be useful upstream

Paths are inside our (private) repository and are given for orientation only.

### 1. Atomic staged save with a commit marker

`src/spec/soul-file.ts` (`saveSoulDir`, `recoverSoulDir`); test in `tests/atomic-save.test.ts`. A save writes every file into `<soul>/.stage-<ms>-<pid>-<n>/f/...` and fsyncs each one. It then writes a `COMMIT` manifest (the list of files to put and delete) to `COMMIT.tmp`, fsyncs it and renames it to `COMMIT`: that rename is the commit point. Promotion moves staged files into place with renames that are idempotent (a file already moved is skipped), fsyncs the touched directories, and removes `COMMIT` last. `recoverSoulDir` rolls a committed stage forward and ignores an uncommitted one unless it is more than an hour old. The invariant: a crash leaves either the old file set or the complete new one, never a mix of files from two saves. The test kills a writer with SIGKILL in a loop and checks the directory after each kill.

For comparison, the reference `runtime/storage/file.py` already builds a sibling temp directory, fsyncs it, and swaps it in through a `.bak` with a load-time `.bak` promotion (#282). Ours differs in that the commit point is a single atomic rename of a manifest and recovery always rolls forward, so there is no window in which the canonical directory is absent. We have not tested the reference under a kill loop and make no claim about its behaviour there.

### 2. Per-session append-only observation journal with atomic orphan adoption

`src/pi/journal.ts`. Each process appends only to its own `<root>/journal/<pid>-<hex>.jsonl`, with records `add` (an exchange awaiting analysis) and `done` (analysis completed). A session never opens a live session's file. A file whose pid is dead is adopted by renaming it to the adopter's own name, which is atomic so exactly one racing process wins; the adopter replays the entries and unlinks the file. A torn last line is skipped, and the file is compacted past 256 KB. Delivery is at-least-once. This removes both the read-modify-write loss of a shared pending file and the failure where a second session takes the first session's pending observations. This is a crash-recovery log, not the §8 org journal.

### 3. Cross-process lease instead of last-writer-wins

`src/pi/lease.ts`; the writer-side check is in `src/pi/worker-client.ts` and `src/pi/worker/soul-worker.ts`. A lease file `<root>/locks/<soul>.lease` holds `pid`, `host`, `session`, `token` and a timestamp. Acquisition uses `open(..., "wx")`. A lease is stale when its pid is dead on the same host, or when it is older than 60 s; an unreadable file is stale after 5 s. Takeover renames the stale file aside and retries at most three times, and puts the file back if it turns out to have displaced a live lease. Nothing ever blocks waiting. In `enforce` mode the persistence worker re-checks that the lease still carries its token before committing, and refuses the save otherwise. The rollout modes are `warn` (default), `enforce` and `off`. The invariant: two sessions on the same soul cannot both commit; the loser is told, not silently overwritten. We did not find any cross-process locking in `src/soul_protocol/` (searched for lease, flock, fcntl, filelock); this may simply not be needed in the reference's deployment model.

### 4. Automatic learning distillation on every observation

`src/runtime/soul.ts` (`learn`, `distill`, `interactionKey`), `src/runtime/evaluation.ts`. After the rubric evaluation of an exchange, a `LearningEvent` is created automatically when the score is notable (>= 0.8 or <= 0.3). Creation is idempotent per interaction, keyed on an explicit interaction id or a hash of the timestamp and participants, and the automatic path applies a 10-minute per-domain cooldown so a run of strong turns does not flood procedural memory. The explicit learn call becomes a re-run that returns the existing event instead of the only trigger.

### 5. Mood as a valence EMA with decay

`src/runtime/state.ts` (`MOOD_ALPHA`, `MOOD_SHIFT`, `applyInteraction`, `recoverState`). Mood is derived from the EMA of valence on every turn, including turns where the EMA is below the shift threshold, where mood returns to a neutral-family value instead of keeping the previous string. The EMA is persisted with the state, and after more than two idle hours it decays with a 6-hour half-life; a valence-driven mood is reset to `neutral` once the EMA is below the threshold. The invariant: a soul cannot stay on a negative mood string indefinitely. See the separate issue for the corresponding observation about the reference implementation.

### 6. Bounded sentiment magnitude instead of a ratio

`src/runtime/psychology.ts` (`heuristicSentiment`). `valence = (pos - neg) / (pos + neg + 1.5)`. The constant in the denominator means a single sentiment word cannot saturate the scale. Negation and intensifiers are scoped to one clause; technical negatives (`bug`, `error`, `crash`, ...) are down-weighted by half because they describe the task rather than the mood; each word counts once.

### 7. Observability of idle work

`src/runtime/idle-log.ts`. A per-soul append-only `idle.jsonl` records every dream, reflect and distill run: kind, origin, engine, result (`ok`, `noop`, `error`), counts and a truncated note. It rotates at 64 KB and has a read surface (`/soul-idle`, `soul_admin idle`). A runtime that works while no session is open becomes observable, and failures of background work are visible.

### 8. Auditable payloads without leaking content

`src/runtime/trust.ts` (`hashContent`, `countRawPayloads`). Trust-chain payloads for new entries carry a sha256 of user-provided text instead of the text, so a deletion request cannot leave the deleted text behind in a signed, append-only log. `countRawPayloads` reports how many legacy entries still carry raw text. §10A.1 already stores only a payload hash; this note is about the payload field in our non-conformant format, and the counter for legacy residue.

## Deviations we chose deliberately

- No SQLite journal: the host runs one process per soul, so the lease plus per-session files cover our concurrency needs. This is a reason we have not built §8, not a claim that §8 is unnecessary.
- The closed `MemoryType` union is kept for type safety in the port. The layer map stays open.
- No CLI and no MCP server: the host agent provides that surface through tools and slash commands.
- No adoption of the §10A trust-chain format yet: our chain predates it.

## Feedback

We would welcome comments from the maintainers on the mechanisms above, in particular 1 (staged save), 3 (lease) and 5 (mood decay), and on whether a short list of third-party implementations under `docs/implementations/` is something you want. We are happy to change the wording of any conformance statement here if it misreads the spec, and to close the gaps in the tables in the order you consider most useful.
