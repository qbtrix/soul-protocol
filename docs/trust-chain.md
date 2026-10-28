# Trust Chain — verifiable action history

The trust chain is a soul's append-only signed log of every audit-worthy action it has performed. It is the cryptographic proof of what a soul learned, when, and from whom.

This page covers:

- [Why a trust chain](#why-a-trust-chain)
- [Threat model — what it does and doesn't protect](#threat-model)
- [What is signed, what isn't](#what-is-signed-what-isnt)
- [Verifying a chain externally](#verifying-a-chain-externally)
- [Key management](#key-management)
- [Sharing a soul without leaking the signing key](#sharing-a-soul-without-leaking-the-signing-key)
- [On-disk layout](#on-disk-layout)
- [Chain pruning](#chain-pruning)
- [API quick reference](#api-quick-reference)

## Why a trust chain

A soul that carries memories across sessions, devices, and platforms only matters if its history can be trusted. Without a verifiable chain, a soul's claims about what it learned are just claims — anyone with file write access can rewrite the past.

The trust chain closes that gap. Every learning event, memory mutation, evolution step, and bond change appends a signed entry. Each entry references the previous one's hash, so altering any entry invalidates every entry after it. Verification with `soul verify` runs in milliseconds and either accepts the chain whole or points at the first broken entry.

This is the foundation we need for:

- **Reputation systems** — agents can verify each other's history before trusting recommendations
- **Provenance proofs** — a soul can prove that a specific learning event preceded a specific decision
- **Regulated deployments** — compliance regimes that require an immutable audit trail
- **Cross-platform migration** — when a soul moves from one runtime to another, the destination can verify nothing was injected during transit

## Threat model

The trust chain protects against:

| Threat | How it's caught |
|---|---|
| Tampering with a past entry's content | Hash chain breaks; `verify_chain()` returns False at the changed entry |
| Forging a signature without the private key | Signature verification fails using the embedded public key |
| Inserting a fake entry in the middle | The next entry's `prev_hash` no longer matches; chain breaks |
| Reordering entries | Sequence numbers go non-monotonic; chain breaks |
| Replaying genesis entry | Duplicate seq detected by `verify_chain()` |
| Future-dated entries | Entries more than 60s ahead of the verifier's clock are rejected (clock-skew tolerance) |
| Backdated entries | An entry whose timestamp falls more than 60s before its predecessor is rejected (#199). Combined with the hash chain, backdating into the middle of the chain breaks `prev_hash`; backdating into the head is now caught by the monotonicity rule |
| Forging a seq gap to hide a tampered entry | Only `chain.pruned` entries may break monotonicity; every other action with a non-`prev.seq + 1` seq fails verification |

The trust chain does **not** protect against:

| Limit | What you need instead |
|---|---|
| Truncation (lopping off the most recent N entries) | A receiver-side policy that pins the latest known head externally — out of scope for the chain itself |
| Compromise of the soul's private key | Once leaked, an attacker can append valid entries; rotate keys and republish |
| Censorship of which entries get appended in the first place | The chain only attests to what was signed; it cannot force a soul to record a given action |
| Confidentiality of payload content | Payloads are stored as hashes only — see [What is signed](#what-is-signed-what-isnt). The actual memory contents live in their own tier files, which are protected by the soul's encryption layer (`Soul.export(password=...)`) |
| External-time correctness | The chain records the soul's local clock, not a trusted time authority. Use a notary or timestamping service if you need external-time anchoring |

## What is signed, what isn't

Every `TrustEntry` contains:

```
seq           — monotonic 0-indexed position in the chain
timestamp     — UTC time the entry was signed
actor_did     — DID of the signer (usually the soul's own DID)
action        — dot-namespaced action name (memory.write, evolution.applied, …)
payload_hash  — SHA-256 hex of canonical JSON of the action's payload
prev_hash     — SHA-256 hex of the previous entry, or GENESIS_PREV_HASH
signature     — Ed25519 signature (base64) over the canonical JSON of the entry minus signature minus summary
algorithm     — "ed25519"
public_key    — base64 of the raw 32-byte public key, embedded so verifiers don't need an external key registry
summary       — short human-readable description of the action (e.g. "3 memories", "+0.50 for alice"). NOT signed
```

Two fields are excluded from the canonical bytes used for hashing and signing: `signature` (because it's the result of signing, so it can't be part of its own input) and `summary` (a non-cryptographic annotation added in #201). Excluding `summary` from the canonical bytes means tooling can rewrite entry summaries — for example, to localise them or to match a more recent formatter — without breaking `verify_chain()`.

The runtime ships an action-keyed default formatter registry (`_SUMMARY_FORMATTERS` in `soul_protocol.runtime.trust.manager`) that fills in a sensible summary at append time when the caller doesn't pass an explicit `summary=`. Callsites in `Soul` (memory writes, supersedes, forgets, evolution proposals/applies, learning events, bond changes) either accept the registry default or pass an explicit summary when the default would be lossy (e.g. `evolution.applied` resolves the trait name from history because the chain payload only carries `mutation_id`).

What is NOT in the chain:

- **The actual payload contents.** Only `payload_hash`. So a chain entry says "the soul wrote 3 memories with IDs `m1, m2, m3`" — not the text of those memories. The text lives in `memory/episodic.json` etc., outside the chain. The `summary` field is a short prose description, not the payload — it's the human-readable equivalent of the action namespace, not a recovery of the data.
- **PII or content from the user side.** If the action.payload had a user's email in it, only the hash of the JSON containing that email is on chain. The hash is not reversible.
- **Recall results.** Recall is read-only — it doesn't mutate state, so it doesn't need a chain entry. (You can layer a separate retrieval-trace receipt on top via `RetrievalTrace`.)

This is intentional: the chain stays compact (kilobytes per thousand entries instead of megabytes), and verification only needs the action sequence, not the action data.

`compute_payload_hash` accepts a plain dict of JSON-native primitives and refuses Pydantic models at the public entry point (#205). If your action carries a BaseModel-shaped payload, call `payload.model_dump(mode="json")` first — this guarantees that two callers who think they are passing the same payload (one as a BaseModel, one as a dict) compute the same hash. The hashing helper also rejects `datetime`, `Path`, and other non-JSON-native nested values (#200) so canonical JSON stays byte-identical across Python versions; pre-serialize via `.isoformat()` or `str()` as appropriate.

## Verifying a chain externally

The simplest path is the CLI:

```bash
soul verify path/to/soul          # exits 0 on valid, 1 on tampering
soul verify path/to/soul --json   # machine-readable output
```

For programmatic verification:

```python
from soul_protocol.runtime.soul import Soul

soul = await Soul.awaken("path/to/soul")
valid, reason = soul.verify_chain()
if not valid:
    raise RuntimeError(f"Chain tampered: {reason}")
```

Or directly from the spec layer (no runtime needed) when you only have the chain JSON:

```python
from soul_protocol.spec.trust import TrustChain, verify_chain

chain = TrustChain.model_validate_json(chain_json_bytes)
valid, reason = verify_chain(chain)
```

The spec-layer verification path requires only `pydantic` and `cryptography` — both already in the base install. No private keys are needed; every entry carries its own public key.

## Key management

Each soul owns an Ed25519 keypair. The keys live under `keys/` inside the soul archive or directory:

```
keys/
  public.key      — raw 32 bytes, always present after first save
  private.key     — raw 32 bytes, present only when explicitly retained
  previous.keys   — newline-separated base64 of rotated-out public keys
                    (only written when the allow-list is non-empty; #204)
```

The keypair is generated on first `Soul.birth()` and persists across saves and awakens.

Verification needs only the public key, and every chain entry already embeds a copy of the public key it was signed under. So a soul shared without `private.key` is still verifiable — just not extensible.

### Key rotation (#204)

A soul can rotate its signing key without invalidating prior chain entries by registering the rotated-out public key in `Keystore.previous_public_keys` before installing the new keypair. `Soul.verify_chain` then accepts entries whose `public_key` matches either the current loaded key or any key in the allow-list.

```python
# Before installing the new keypair, record the old public key.
old_pub = soul._keystore.public_key_bytes
soul._keystore.add_previous_public_key(old_pub)

# Install the new keypair (one of several ways — depends on your runtime).
new_provider = Ed25519SignatureProvider()
soul._signature_provider = new_provider
soul._trust_chain_manager.provider = new_provider
soul._keystore.public_key_bytes = new_provider.public_key_bytes
soul._keystore.private_key_bytes = new_provider.private_key_bytes

# Verification now accepts the mixed-signer chain.
valid, _ = soul.verify_chain()
```

**Default behavior is unchanged.** An empty `previous_public_keys` keeps the v0.4.0 strict-current-key binding, so a soul that never rotates keys sees no behavioral difference.

**Forward compatibility note.** `previous.keys` is a forward-compatible field. A runtime that doesn't recognize the file (older soul-protocol releases, third-party verifiers that haven't adopted #204) will simply ignore it and fall back to strict-current-key binding — which means they'll reject the rotated chain. This is the safe failure mode: a verifier never accepts a chain it can't fully validate.

A `soul rotate-keys` CLI helper is planned for a follow-up v0.5.x release. Today the rotation flow is API-driven via `Keystore.add_previous_public_key()` plus a manual provider swap.

## Sharing a soul without leaking the signing key

Use `Soul.export(path, include_keys=False)` (the default). This drops `keys/private.key` from the archive but keeps `keys/public.key` and the full `trust_chain/`. The recipient can:

- Read the chain
- Verify the chain
- Awaken the soul and inspect memories

The recipient cannot:

- Append new chain entries under the original soul's DID (no private key)
- Sign anything that would pass `verify_chain()` against the original public key

When the recipient calls `Soul.observe()` or any other state-changing method on a soul loaded without a private key, the underlying action still happens (memory writes, bond updates) but **no chain entry is appended**. The recipient's chain stays at the length it was when received.

If you want to give the recipient the signing key — for instance migrating between your own devices — pass `include_keys=True`:

```python
await soul.export("backup.soul", include_keys=True)  # only do this on trusted destinations
```

`Soul.save()` and `Soul.save_local()` default to `include_keys=True` because they're meant for the owner's own machine. `Soul.export()` defaults to `include_keys=False` because exports are usually for sharing.

## On-disk layout

In a `.soul` zip archive or a `.soul/` directory:

```
trust_chain/
  chain.json         — canonical Pydantic-serialized TrustChain (the source of truth on load)
  entry_000.json     — human-readable copy of seq 0
  entry_001.json     — human-readable copy of seq 1
  ...
keys/
  public.key
  private.key        — only when include_keys=True
  previous.keys      — newline-separated base64; only when previous_public_keys is non-empty (#204)
```

The per-entry JSON files are for human inspection and debugging — `chain.json` is what the runtime reads. Chains are not encrypted independently of the soul; if the surrounding soul archive is password-encrypted (`Soul.export(password=...)`), the chain entries are encrypted at rest too.

## Chain pruning

A soul that runs for years accumulates a long chain — every memory write, every bond change, every learning event becomes a signed entry. Without bounds, the chain grows unboundedly. Touch-time pruning (v0.5.0, issue #203) puts a configurable cap on the chain length and compresses old history into a single signed marker.

### Configuring the cap

`Biorhythms.trust_chain_max_entries` defaults to `0`, which disables pruning and preserves the prior unbounded-chain behaviour. Set it to a positive integer to cap the chain at that length:

```python
from soul_protocol import Soul

soul = await Soul.birth(
    "AlwaysOn",
    biorhythms={"trust_chain_max_entries": 500},
)
```

When the cap is reached, the next `append()` call collapses every non-genesis entry into a single signed `chain.pruned` marker before writing the new entry. With a cap of N, the chain steady-state length is bounded by `min(N, total_appends_since_last_prune + 2)`.

### The `chain.pruned` marker

Every prune writes one signed entry with `action == "chain.pruned"` and a payload that records what was dropped:

```
{
  "count":     int,    // number of entries dropped
  "low_seq":   int,    // lowest seq number that was dropped
  "high_seq":  int,    // highest seq number that was dropped
  "reason":    str,    // "touch-time" for auto-prune, "manual" for CLI/MCP, free-form
}
```

The marker carries `seq = high_seq + 1` so the audit counter never resets — replays of the chain on a peer that observed the older entries can spot the gap. `prev_hash` links from the genesis entry's hash, NOT from the highest-pruned entry.

### Verification rule

The verifier permits exactly one carve-out from strict seq monotonicity: an entry whose `action == "chain.pruned"` MAY have a seq strictly greater than `prev.seq + 1`. The `prev_hash` linkage and signature still apply normally. Every other action remains strictly monotonic (`seq == prev.seq + 1`), so a tampered chain that injects a gap at any other action name fails verification.

The constant `CHAIN_PRUNED_ACTION = "chain.pruned"` is exported from `soul_protocol.spec.trust` so external verifiers in other languages know which action receives the carve-out.

### Manual pruning

The `soul prune-chain` CLI command and the `soul_prune_chain` MCP tool let operators trigger a prune outside of the auto-prune path. Both default to dry-run; pass `--apply` (or `apply=True`) to mutate the chain:

```bash
soul prune-chain ./.soul --keep 100             # preview
soul prune-chain ./.soul --keep 100 --apply     # execute
soul prune-chain ./.soul --keep 100 --json      # machine-readable
```

When `--keep` is omitted the command falls back to the soul's `Biorhythms.trust_chain_max_entries`. With both unset the command exits non-zero with a clear error.

### What the stub does NOT do (deferred to v0.5.x)

This is the touch-time stub. The full archival design lands in a later v0.5.x release and adds:

- A separate `trust_chain/archive/` directory that retains the dropped entries instead of discarding them
- `chain.archived` checkpoint entries that span the active chain and the archive files
- Compression of the archived entries
- Verification across the active + archived chain split

The stub trades full retention for simplicity: a single signed marker preserves the audit metadata about what was dropped (count, seq range, reason), but the original entries themselves are gone. An operator who needs full retention should either set the cap to 0 (unbounded) or wait for the v0.5.x archival release.

## API quick reference

Spec layer (`soul_protocol.spec.trust`):

- `TrustEntry`, `TrustChain` — Pydantic models
- `SignatureProvider` — Protocol; runtime supplies an Ed25519 implementation
- `verify_entry(entry, prev_entry, provider=None) -> bool`
- `verify_chain(chain) -> tuple[bool, str | None]`
- `chain_integrity_check(chain) -> dict` — `{valid, length, first_failure, signers}`
- `compute_payload_hash(payload) -> str`
- `compute_entry_hash(entry) -> str`
- `GENESIS_PREV_HASH` — `"0" * 64`
- `CHAIN_PRUNED_ACTION` — `"chain.pruned"` — the only action whose entries may break seq monotonicity

Runtime layer:

- `soul_protocol.runtime.crypto.ed25519.Ed25519SignatureProvider`
- `soul_protocol.runtime.crypto.keystore.Keystore`
- `soul_protocol.runtime.trust.manager.TrustChainManager`
- `TrustChainManager.prune(keep=None, *, reason="touch-time") -> dict`
- `TrustChainManager.dry_run_prune(keep=None) -> dict` — preview without mutation
- `TrustChainManager.max_entries: int` — cap mirrored from `Biorhythms.trust_chain_max_entries`

Soul-level convenience:

- `soul.trust_chain` — read-only `TrustChain`
- `soul.trust_chain_manager` — `TrustChainManager` for advanced use
- `soul.verify_chain()` → `(valid, reason)`
- `soul.audit_log(action_prefix=None, limit=None)` → `list[dict]`

CLI:

- `soul verify <path>` — exit 0/1
- `soul audit <path> --filter memory. --limit 20` — Rich table or `--json`
- `soul prune-chain <path> [--keep N] [--apply]` — touch-time prune, dry-run by default

MCP tools:

- `soul_verify` — JSON `{soul, did, valid, length, signers, first_failure}`
- `soul_audit` — JSON `{soul, did, entries: […]}`
- `soul_prune_chain` — JSON `{soul, did, applied, summary, chain_length, keep}`
