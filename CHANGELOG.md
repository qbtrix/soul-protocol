# Changelog

All notable changes to soul-protocol are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **`soul journal` shell-hook subcommand (#189)** — three new commands wrap the org-level SQLite WAL journal as a CLI for shell hooks, CI scripts, and non-Python runtimes. `soul journal init <path>` bootstraps a standalone journal file (no root soul, no scope tree). `soul journal append <path>` writes one event from `--action` / `--actor` / `--payload` / `--scope` / `--causation-id` flags, or batches JSONL events from `--stdin`. The committed `EventEntry` is echoed to stdout as JSON (with backend-assigned `seq` and `prev_hash`) so callers can capture event ids for downstream causation chains. `soul journal query <path>` filters by `--action`, `--action-prefix` (with trailing-dot tolerance), `--scope`, `--correlation-id`, `--since` / `--until`, plus `--at <iso>` for point-in-time replay. Default output is a Rich table; `--json` emits a JSON array. Foundation for replacing memory-heavy `soul-sync.sh` hooks with structured journal events.
- **Soul-aware evals (#160)** — a YAML-driven format and runner for evaluating memory-driven agents. Specs seed the soul with explicit state (memories, OCEAN, bonds, mood, energy) before each case runs, so the eval measures behaviour against a known starting point rather than treating the soul as a stateless function. Five scoring kinds: `keyword` (case-insensitive substring match), `regex` (Python regex), `semantic` (Jaccard-with-containment token overlap), `judge` (LLM-as-judge against free-form criteria), and `structural` (programmatic checks on output and soul state — bonded-user mention, mood-after, energy bounds, recall set membership). Cases run in either `respond` mode (the runner builds a system prompt + per-turn context block and asks the engine for a reply) or `recall` mode (`Soul.recall(query=message, ...)`). Without an engine the runner produces a deterministic fallback so keyword / regex / semantic / structural cases still pass; judge cases skip cleanly rather than fail. New `soul eval` CLI command runs one spec or every `.yaml` under a directory; `--json`, `--filter`, `--judge-engine`, `--verbose` options. Exit code 0 when every case passes (skipped cases don't fail the run); 1 on any failure or spec error. New `soul_eval` MCP tool runs a YAML spec against the active soul (seed block ignored — the soul's live state is the seed) so an agent can self-evaluate. Five shipped example specs under `tests/eval_examples/` cover personality expression, multi-user memory filtering, domain isolation, bond-strength gating, and trust chain provenance — wired into pytest as smoke tests. Foundation for the v0.4.x intelligence bundle (#142 soul optimize will plug into this measurement signal). Full doc at `docs/eval-format.md`.

### Trust chain hardening

- **Timestamp monotonicity in `verify_chain` (#199)** — the spec-layer verifier now rejects entries whose timestamp predates the previous entry's timestamp by more than 60 seconds (skew tolerance). Closes a backdating gap where an attacker who briefly held the private key could write entries with backdated timestamps to insert events "into the past" of the chain. The hash chain caught mid-chain insertion already; this rule catches head replacement with past-dated entries.
- **Strict canonical JSON for hashing (#200)** — `spec.trust._canonical_json` no longer silently stringifies non-JSON-native values via `default=str`. A new `_strict_default` raises `TypeError` with an actionable message ("pre-serialize datetimes via `.isoformat()`, Pydantic models via `.model_dump(mode='json')`, Path objects via `str()`"). Hash determinism across Python versions is now enforced rather than assumed. Existing chain-append payloads in `runtime/soul.py` and `runtime/bond.py` were audited and continue to work — they were already JSON-native; `default=str` was masking nothing in production but could have masked drift if a future caller passed a `datetime` directly.
- **Tighter typing on `compute_payload_hash` (#205)** — the public `compute_payload_hash(payload: dict)` now refuses `BaseModel` inputs at the entry point with a `TypeError`. Two callers passing a logically-equivalent BaseModel and dict could otherwise produce different hashes. The internal `compute_entry_hash` (which IS passed a Pydantic `TrustEntry`) is unchanged — only the public payload helper gets the guard.
- **Key rotation support (#204)** — `Keystore` gains `previous_public_keys: list[bytes]`, persisted alongside `keys/public.key` and `keys/private.key` as `keys/previous.keys` (newline-separated base64). `Soul.verify_chain` now accepts entries whose `public_key` matches EITHER the current loaded key OR any key in the allow-list. Default empty allow-list keeps the v0.4.0 strict-current-key behavior — opt-in for callers that rotate keys. Older runtimes that don't honor the allow-list will reject rotated chains, which is the safe failure mode (forward-compatible field). The `soul rotate-keys` CLI is intentionally not part of this bundle — runtimes that want to rotate keys today can do so by appending the old public key bytes to `Keystore.previous_public_keys` before installing the new keypair.

### Trust-chain observability

- **Audit-log payload summaries (#201)** — `TrustEntry` gains a non-cryptographic `summary` field that carries a short human-readable description of the action (e.g. `"3 memories"`, `"+0.50 for alice"`, `"replaced abc12345 with def67890"`). The summary is stored on the entry but excluded from the canonical bytes used for hashing and signing, so callers can edit, localise, or rewrite the summary without breaking `verify_chain()`. `TrustChainManager.append` accepts a new `summary=` parameter; when omitted, an action-keyed default formatter registry (`_SUMMARY_FORMATTERS`) fills it in for the action namespaces Soul actually emits — `memory.write`, `memory.forget`, `memory.supersede`, `bond.strengthen`, `bond.weaken`, `evolution.proposed`, `evolution.applied`, `learning.event`. `Soul.audit_log()` rows now include the `summary` key. The `soul audit` CLI gains a `Summary` column in its Rich table and a `--no-summary` flag for the hash-only view from 0.4.0; JSON output always carries `summary`. Pre-#201 chain entries load with `summary=""` and verify unchanged. Soul callsites for `evolution.applied` and `learning.event` now pass an explicit summary because their on-chain payloads don't carry the trait/score keys the registry default needs (incidental fix surfaced during the audit).
- **Structured chain-append-failure logging (#202)** — `Soul._safe_append_chain` no longer collapses every skip into a single DEBUG line. The verification-only path (souls loaded without a private key, or with `_PublicOnlyProvider`) keeps DEBUG so observability isn't noisy for the documented read-only flow. An *unexpected* exception during `manager.append` (real `ValueError`, `RuntimeError`, or `TypeError` from `sign()` or downstream) now logs at WARNING under the `runtime.chain_append_skipped` event tag with `action`, `error_type`, `error`, and `soul` fields — observability surfaces should treat this as an audit-trail gap rather than the routine read-only behaviour the previous DEBUG line implied. The `BondRegistry` `on_change` callback failure path follows the same pattern under `runtime.bond_callback_failed`. The underlying state mutation (memory write, bond strengthen, etc.) still completes either way — only the chain-side signing was lost.

---

## [0.4.0] -- 2026-04-29

The **identity bundle** release. Major bump because the schema grows and the API surface gains new top-level concepts: users, memory layers + domains, and signed action history. One coherent migration; not three rounds.

### Identity bundle

- **Multi-user soul support (#46)** — a single soul can now serve multiple humans without bleeding context. `soul.observe()` and `soul.recall()` accept a `user_id` parameter; memory retrieval filters by user context; the bond system tracks per-user relationship strength. The `.soul` file already supported multiple bond entries — this wires runtime context-switching on top.
- **User-defined memory layers + domain isolation (#41)** — at the spec layer, `MemoryEntry.layer` is a free-form string. `LAYER_CORE`, `LAYER_EPISODIC`, `LAYER_SEMANTIC`, `LAYER_PROCEDURAL`, `LAYER_SOCIAL` ship as well-known constants (and the runtime `MemoryType` StrEnum keeps the same values for back-compat — `MemoryType.SEMANTIC == "semantic"`). `MemoryEntry` gains an optional `domain` field (e.g. `"finance"`, `"legal"`, `"personal"`) defaulting to `"default"`. `MemoryStore` queries can scope to layer + domain. New `social` layer for relationship memory powered by `SocialStore`. `MemoryManager.layer(name)` returns a `LayerView` that works for built-in and user-defined layer names alike. `Soul.remember(domain=...)`, `Soul.observe(domain=...)`, and `Soul.recall(layer=..., domain=...)` accept the new filters. `DomainIsolationMiddleware` enforces that callers only read their authorized domains and raises `DomainAccessError` on writes outside the allow-list. Existing `.soul` files load with `layer` derived from `type` and `domain="default"`; the on-disk layout switches to a nested `memory/<layer>/<domain>/entries.json` form only when custom domains or layers are present. New CLI: `soul layers <path>` lists per-layer + per-domain counts.
- **Trust chain — verifiable action history (#42)** — every learning event, memory mutation, and evolution step is signed and traceable. New spec primitives in `soul_protocol.spec.trust`: `TrustEntry`, `TrustChain`, `SignatureProvider` protocol, plus `verify_chain`, `verify_entry`, `chain_integrity_check`, `compute_payload_hash`, `compute_entry_hash`, `GENESIS_PREV_HASH`. Default `Ed25519SignatureProvider` ships with the runtime. Append-only Merkle-style chain per soul: `trust_chain/chain.json` is the canonical store, `trust_chain/entry_NNN.json` adds per-entry copies for human inspection. Signing keys live under `keys/public.key` and `keys/private.key`; `Soul.export(include_keys=False)` (default) drops the private key for safe sharing while keeping the chain verifiable. Soul-level helpers: `soul.trust_chain`, `soul.trust_chain_manager`, `soul.verify_chain()`, `soul.audit_log()`. Memory writes (observe), supersedes, forgets, evolution proposed/applied, learning events, and bond strengthen/weaken all auto-append signed entries. New CLIs: `soul verify <path>` checks integrity (exit 1 on tampering); `soul audit <path>` prints a Rich timeline with `--filter <prefix>`, `--limit N`, and `--json`. New MCP tools: `soul_verify`, `soul_audit`. Full doc at `docs/trust-chain.md` covers the threat model, key management, and how to share souls without leaking the signing key. Foundation for reputation systems and provenance proofs.

### Rolled-in polish

- **Density-driven focus (#194)** — `SoulState.focus` is now computed from a sliding window of recent interactions instead of being a static default. Bands: 0 in window → `low`, 1-2 → `medium`, 3-9 → `high`, 10+ → `max`. Manual lock via `soul.feel(focus="<level>")`; `feel(focus="auto")` clears the lock. New `Soul.recompute_focus(now)` for read-time freshness. CLI status + MCP `soul_state` refresh focus before display.
- **Memory update primitives (#193)** — `Soul.supersede(old_id, new_content, *, reason, ...)` writes a new memory and links the old one's `superseded_by` for provenance. `Soul.forget_one(memory_id) -> dict` for audited single-id deletion. New CLIs: `soul supersede` and `soul forget --id`. Fixes a long-standing bug where `soul forget` reported `0 memories` even on successful deletion (was reading the wrong dict key).
- **Wiki rebuild (#186)** — fresh wiki regeneration covering 328 articles after the 0.3.3/0.3.4 surface changes.

### Schema migrations

Existing `.soul` files load cleanly. The migration tool (`soul migrate <path>`) upgrades older souls in place:

- `MemoryEntry` gains optional `user_id` (None for legacy entries — they belong to the soul's default bond) and `domain` (defaults to `"default"`).
- Memory directory layout migrates from `memory/{episodic,semantic,procedural}.json` to `memory/{layer}/{domain}/entries.json` on first save. The legacy flat layout is read transparently for back-compat.
- `trust_chain/` directory is created on first signed action; older souls have an empty chain until they perform a signed action.

### Breaking changes

- At the spec layer, `MemoryEntry.layer` is now a plain `str` rather than an enum. `LAYER_CORE`, `LAYER_EPISODIC`, `LAYER_SEMANTIC`, `LAYER_PROCEDURAL`, `LAYER_SOCIAL` are exported from `soul_protocol.spec.memory` for code that wants well-known names. The runtime `MemoryType` StrEnum is unchanged (still importable from `soul_protocol.runtime.types`); members compare equal to the new layer strings (`MemoryType.SEMANTIC == "semantic"`). Downstream code that pattern-matched against the spec-layer enum values needs to compare strings instead.
- `Soul.observe(user_id=None, ...)` adds a keyword-only parameter ahead of the existing args. Positional callers should switch to keyword form (the existing tests already do).
- `Soul.recall(query, *, user_id=None, layer=None, domain=None, ...)` similarly adds keyword-only filters. Default behavior is unchanged when these are omitted.

### Notes

- This release rolls in three polish PRs (#194, #193, #186) that were in flight on `dev` between 0.3.4 and 0.4.0. Their commits are preserved in the release branch as separate logical units.
- Closes issues #46, #41, #42 (the identity bundle umbrella tracker #183 stays open as the parent and gets closed when this release tags).

---

## [0.3.4] -- 2026-04-24

Hotfix release. The 0.3.3 wheel failed to upload to PyPI because `pyproject.toml` had a redundant `[tool.hatch.build.targets.wheel.force-include]` block that double-included the bundled template YAMLs (`analyst.yaml`, `arrow.yaml`, `cyborg.yaml`, `flash.yaml`). PyPI rejected the wheel with HTTP 400 ("Duplicate filename in local headers"). The 0.3.3 source distribution did upload, so `pip install soul-protocol==0.3.3` still works via the sdist — but a clean wheel install requires 0.3.4.

### Fixed

- Removed the redundant `force-include` for `src/soul_protocol/templates`. Templates already ship through the package-level auto-discovery; the explicit force-include duplicated them in the ZIP and broke PyPI upload. (Fixes the 0.3.3 wheel build.)

### Notes

- All 0.3.3 features remain unchanged. This is a packaging fix only.
- PyPI does not allow re-uploads of the same version, even after deletion — that's why this is 0.3.4 rather than a re-cut of 0.3.3.

---

## [0.3.3] -- 2026-04-24

The "headless standard" release. soul-protocol is now positioned as a language-agnostic standard with a Python reference implementation. The 0.3.2 number was skipped — its scope rolled into 0.3.3 alongside the rest of the #97 visibility work.

### Added

- **Language-agnostic standard** — new `docs/SPEC.md` describes Soul Protocol independent of the Python reference implementation. Anyone implementing in Rust, Go, TypeScript, or a custom runtime reads this file. Covers file format, identity, memory tiers, scope grammar, journal contract, retrieval vocabulary, `CognitiveEngine` protocol, conformance checklist, and versioning policy. (#179)
- **README "standard vs reference impl" fork** — the top of the README routes implementation-builders to SPEC.md and Python consumers to the rest of the README. (#179)
- **Journal primitives (5)** that the spec now requires of any conforming implementation:
  - `#1` `Journal.append(entry)` returns the committed `EventEntry` with the backend-assigned `seq` + `prev_hash`.
  - `#2` `Journal.query(action_prefix=...)` — prefix match on dot-separated action names.
  - `#3` Typed `DataRef` for retrieval candidates — `RetrievalCandidate.content` is a typed model (dicts with `kind="dataref"` promote automatically).
  - `#4` `RetrievalRequest.point_in_time` — native UTC datetime field replacing the `@at=...|query` string hack for time-travel queries.
  - `#5` Async `SourceAdapter.aquery` + `RetrievalRouter.adispatch` — adapters backed by async-native SDKs can participate in cooperative multitasking without bridging through `asyncio.run`.
- **Spec-level retrieval vocabulary** — `spec/retrieval.py` absorbed the Protocol types (`SourceAdapter`, `AsyncSourceAdapter`, `CredentialBroker`), the `Credential` data class, and the `RetrievalError` exception hierarchy (`NoSourcesError`, `SourceTimeoutError`, `CredentialScopeError`, `CredentialExpiredError`). These are the types a conforming implementation builds against. (#179)
- **`tests/spec/test_retrieval.py`** — spec-level tests for `Credential` field validation, `Credential.is_expired()` boundary behavior, and `isinstance()` conformance against the `SourceAdapter` / `AsyncSourceAdapter` Protocols. (#179)
- **Safety net for destructive CLI commands** — `soul cleanup` and `soul forget` are now dry-run by default and require an explicit `--apply` flag to execute. Before any destructive save, a side-by-side `.soul.bak` backup is written next to the soul file so an accidental `--auto` run is recoverable with a single `cp`. The prior behavior where `soul cleanup --auto` silently deleted hundreds of memories is gone. Closes #148. (#181)
- **System prompt safety guardrails** — `Soul.to_system_prompt()` now appends a default safety section that instructs the agent to decline requests for core memory contents, bond details, and evolution history. Covers direct asks, indirect framings, and roleplay bypasses. Opt out with `to_system_prompt(safety_guardrails=False)` for transparent deployments. (#185)
- **`Soul.public_profile()`** — returns the safe-to-expose subset of a soul's identity (DID, name, archetype, born, lifecycle, values, OCEAN summary, skill names) for use by registries, peer discovery, or public agent cards. Excludes memory contents, bond details, evolution history, and any internal state. (#185)
- Together with the `MemoryVisibility` tier work shipped in PR #114, the prompt guardrails and `public_profile()` close the remaining surface of #97 (memory visibility and identity verification for public-channel safety).

### Changed

- **Retrieval infrastructure moved out of the spec.** The concrete `RetrievalRouter`, `InMemoryCredentialBroker`, `ProjectionAdapter`, and `MockAdapter` implementations have been removed from `soul_protocol.engine.retrieval` — they are application-layer orchestration and belong in the consuming runtime. The pocketpaw reference runtime ships them at `pocketpaw.retrieval` as of pocketpaw v0.4.17. (#179)
- **`docs/architecture.md` retitled** "Python Reference Implementation" and now links to `docs/SPEC.md` at the top. Makes clear that the patterns in that document (SQLite journal, Damasio/ACT-R/LIDA pipeline, module layout) are one way to honor the spec, not the only way. (#179)
- **Wheel no longer ships `src/soul_protocol/spike/`.** The spike module contains in-progress design experiments that are not part of the shipped API; excluding it from the wheel keeps the installed package focused on the standard + reference runtime. (#179)
- `soul cleanup --auto` no longer executes on its own — it now means "skip the confirmation prompt, assuming `--apply` is also passed." Running `--auto` without `--apply` is a no-op preview. Update any scripts that relied on the old one-flag behavior. (#181)
- `soul forget` gains an `--apply` flag with the same semantics: dry-run by default, `--apply --confirm` to execute non-interactively. (#181)

### Removed

- **`soul_protocol.engine.retrieval` module** — the entire package is gone:
  - `engine/retrieval/__init__.py`
  - `engine/retrieval/adapters.py` (`SourceAdapter`, `AsyncSourceAdapter`, `MockAdapter`, `ProjectionAdapter`)
  - `engine/retrieval/broker.py` (`Credential`, `CredentialBroker`, `InMemoryCredentialBroker`)
  - `engine/retrieval/exceptions.py` (the `RetrievalError` hierarchy)
  - `engine/retrieval/router.py` (`RetrievalRouter`)
- **`tests/test_engine/test_retrieval.py`** — 923-LOC router + broker test suite moved to pocketpaw (`tests/retrieval/test_router.py`) with imports rewritten.

### Migration for third-party callers

If you import from `soul_protocol.engine.retrieval`, update to the new home:

```python
# Before (0.3.1 and earlier)
from soul_protocol.engine.retrieval import (
    Credential, CredentialBroker, SourceAdapter,
    NoSourcesError, SourceTimeoutError,
    CredentialScopeError, CredentialExpiredError,
)

# After (0.3.3)
from soul_protocol.spec.retrieval import (
    Credential, CredentialBroker, SourceAdapter,
    NoSourcesError, SourceTimeoutError,
    CredentialScopeError, CredentialExpiredError,
)
```

If you use the concrete orchestration (`RetrievalRouter`, `InMemoryCredentialBroker`, `ProjectionAdapter`, `MockAdapter`), it now lives in the pocketpaw runtime:

```python
# Before
from soul_protocol.engine.retrieval import RetrievalRouter, InMemoryCredentialBroker

# After
from pocketpaw.retrieval import RetrievalRouter, InMemoryCredentialBroker
```

A third-party runtime implementing Soul Protocol in another language (or a custom Python runtime) is expected to provide its own orchestration; only the vocabulary in `spec/retrieval.py` is part of the standard.

---

## [0.3.1] -- 2026-04-14

### Added

- **Org-level event journal** — append-only event log with SQLite WAL backend, atomic `seq` allocation, and opportunistic hash-chain for tamper evidence. `EventEntry`, `Actor`, and `DataRef` spec types land in `soul_protocol.spec`. Journal entries flow through the org layer for audit and replay. (#165, #172)
- **Decision traces** — three new event types (`agent.proposed`, `human.corrected`, `decision.graduated`) with `causation_id` chaining so a correction links back to the proposal that triggered it. Helpers for building a trace, querying by chain, and clustering recurring correction patterns. This is the core moat — the graduation from "the agent guessed" to "the human decided, and here's the receipt." (#168)
- **Retrieval router + credential broker** — Zero-Copy data federation for the org layer. Router resolves a `DataRef` against registered adapters, broker scopes credentials per source and fails closed with an audit event on any denial. No data is copied into the org boundary; only the receipt is. (#169)
- **`soul org` CLI** — `init`, `status`, and `destroy` commands to bootstrap an org, inspect its current state (root agent, journal head, adapter registry), and tear it down cleanly. `destroy` archives the org to `~/.soul-archives/` before wiping so nothing is ever truly lost on an accident. (#167, #170)
- **Root Agent** — the governance-only agent that sits above the org. Three-layer undeletability (storage-level guard on the file, protocol-level guard in the journal, CLI-level refusal to delete) makes it structurally impossible to remove by accident. Can propose, cannot execute — by design. (#170)
- **Default archives directory** at `~/.soul-archives/` as a sibling of the org directory so `soul org destroy` archives survive a wipe of the org dir itself.
- **`MemoryEntry.scope` + `match_scope` helper** — scope tags on memories with a matcher that uses the spec-level grammar (`org:*`, `agent:<id>`, `session:<id>`, etc.). Recalls can now filter by scope without reaching into tier internals. (#162)
- **`RetrievalTrace` receipt** — every recall now produces a trace with the query, candidate set, rerank decisions, and final selection. Exposed at runtime via `Soul.last_retrieval` so callers can introspect why a given memory surfaced. (#161)
- **Bundled role archetype templates** — Arrow, Flash, Cyborg, and Analyst templates ship with the package. `load_template()` loads them by name, and the new `soul template` CLI lists and instantiates them. (#163)
- **`SOUL_USERS_DIR` env var + improved `--users-dir` default** — user souls now nest under `--data-dir` by default (so `soul org init --data-dir /tmp/foo` keeps founder souls in `/tmp/foo/users/` instead of the real `~/.soul/users/`). The `SOUL_USERS_DIR` env var overrides without a flag, and an explicit `--users-dir` overrides both. The pre-v0.3.1 behavior of always writing to `~/.soul/users/` (regardless of `--data-dir`) silently polluted home directories during CI runs and isolated demos.
- **Framework-agnostic Org Journal Spec** at `docs/org-journal-spec.md` so other implementations can target the same wire format without reading the Python source. (#164)
- **Manual testing guide** at `docs/manual-testing.md` for org-layer flows that are awkward to cover in unit tests. (#164)

### Changed

- Architecture doc trimmed — org-layer detail moved to the dedicated spec so `docs/architecture.md` stays focused on the soul runtime. (#164)
- Doc examples neutralized — replaced PocketPaw-specific wording so the docs land cleanly for anyone using the protocol from their own stack. (#171)

### Fixed


- Bare `pip install soul-protocol` now produces a working `soul` CLI. The CLI's required dependencies (`click`, `rich`, `pyyaml`, `cryptography`) have moved from the `[engine]` extra into base `dependencies`, so `soul --help` no longer raises `ImportError` on a minimal install. The `[engine]` extra is kept as an empty backwards-compat alias so existing `pip install soul-protocol[engine]` pins continue to resolve. (#173, fixes #157)
- `smart_recall` now populates `Soul.last_retrieval` with a `RetrievalTrace` receipt. The original #161 instrumentation covered `recall()` only because `smart_recall` was not on dev at the time; this closes the gap. The trace carries `source="soul.smart"` and metadata flags that record whether rerank ran.
- `match_scope` is now bidirectional containment: a caller with scope `org:sales:leads` matches a memory tagged `org:sales:*` (and vice versa). The previous asymmetric behaviour made bundled archetypes' core memories invisible to agents installed from them. The fix makes the glob-style `default_scope` in Arrow, Flash, Cyborg, and Analyst actually functional out of the box. The old one-way variant is preserved as `match_scope_strict`.

---

## [0.3.0] -- 2026-04-09

### Added
- **Dream cycle** — `Soul.dream()` for offline batch memory consolidation. Reviews accumulated episodes to detect topic clusters (Jaccard token overlap), extract recurring procedures (action signature frequency), detect behavioral trends (topic drift over time), consolidate knowledge graph (merge duplicate entities, prune expired edges), and synthesize cross-tier insights (episodes → procedural memories, behavioral patterns → OCEAN evolution proposals). No LLM required — all heuristic-based.
- `soul dream` CLI command with `--since`, `--no-archive`, `--no-synthesize`, `--dry-run`, `--json` flags. `--dry-run` previews the full report without any destructive mutations so you can see what a cycle would change before committing.
- `DreamReport` dataclass with topic clusters, detected procedures, behavioral trends, graph consolidation stats, evolution insights, and a `dry_run` flag on the report itself.
- **Smart recall** — `Soul.smart_recall()` for LLM-reranked memory retrieval. Fetches a larger candidate pool via heuristic recall, then optionally uses the `CognitiveEngine` to pick the most contextually relevant entries. Opt-in via `MemorySettings.smart_recall_enabled` (default `False`) or a per-call `enabled=` override. Hardened prompt injection defense: memory content is sanitized (angle brackets stripped, response-marker strings redacted) and isolated inside a `BEGIN/END MEMORIES` fence so adversarial memories can't hijack the rerank. 30-second hard timeout on the LLM call so a hung engine can't stall the recall hot path — falls back cleanly to heuristic order on timeout, parse error, or engine failure.
- **Significance short-circuit** — `observe()` now skips entity extraction (step 5) and self-model update (step 6) when an interaction scores below the significance threshold AND fact extraction finds nothing. Saves two LLM calls per trivial interaction. Gated by `MemorySettings.skip_deep_processing_on_low_significance` (default `True`) with an escape hatch (`False`) for callers that need guaranteed extraction. The gate re-checks `significant` after step 4b fact-based promotion so meaningful short messages still get the full pipeline.
- **`soul remember --type`** — the CLI command now accepts `--type/-t episodic|semantic|procedural` to pick which tier a memory lands in. Fixes a long-standing gap where the runtime `Soul.remember()` supported tier selection but the CLI always defaulted to semantic, silently dropping events that callers intended as episodic.

### Changed
- `MemorySettings` gains `smart_recall_enabled` (bool, default False) and `skip_deep_processing_on_low_significance` (bool, default True). Default values preserve previous behavior — no breaking change for existing souls.
- `_dedup_semantic` in the dream cycle now soft-deletes duplicates via `superseded_by` instead of removing them from the underlying dict. Preserves an audit trail and honors any future side effects added to `SemanticStore.remove()`.
- `_count_archivable` in dry-run mode matches `archive_old_memories` exactly (48-hour cutoff, archived filter, min-3 guard) so dry-run counts don't drift from real-run counts.

### Fixed
- CLI `remember` previously dropped `--type` silently because the option didn't exist. Tools passing the flag (like the PocketPaw workspace soul-sync hook) were failing without surfacing the error, leaving episodic tiers empty for extended periods.

### Docs
- `docs/cli-reference.md` now has full sections for `soul remember` and `soul recall` — these were missing from the reference entirely. Includes memory tier guide and full option tables.
- `skills/soul-protocol/SKILL.md` updated with episodic and procedural examples plus a tier guide for agents.
- `docs/getting-started.md` notes the runtime `type` parameter on `soul.remember()` for users reading the Python walkthrough.
- `README.md` (kb-go workspace) adds a "Pairing with Soul Protocol" guide explaining when to reach for each tool and how to bridge them in an agent pipeline.

### Tests
- 2062 tests passing (up from 2010). New test classes: `TestDreamerDryRun`, `TestSignificanceShortCircuit`. New test files: `test_dream.py`, `test_rerank.py`. New CLI tests for `remember --type` with every tier plus invalid-value rejection.

---

## [0.2.9] -- 2026-03-29

### Added
- **Progressive recall** — `recall(progressive=True)` returns primary entries with full content + overflow entries with L0 abstract. Uses `model_copy()` to avoid mutating store objects. `is_summarized` runtime marker on overflow entries
- **Archival memory** — `MemoryManager.archive_old_memories()` compresses episodic entries older than 48h into `ConversationArchive`. Archived entries filtered from recall. Archives persist through export/awaken
- **Auto-consolidation** — `observe()` auto-triggers archival + reflection every `consolidation_interval` (default 20) interactions. `interaction_count` persisted in `SoulConfig`
- **Eternal storage wiring** — `Soul.archive()` method for IPFS/Arweave archival. `EternalStorageManager.with_mocks()` factory. `eternal=` param on `birth()`/`awaken()`. `export(archive=True)` flag
- **Skill decay** — `Skill.decay(days)` reduces XP by 1 per day inactive, floor at 0, never reduces level. `SkillRegistry.decay_all()` runs at start of each `observe()`
- 33 new tests (1977 → 2010)

### Changed
- Skills XP grants now significance-weighted (5-30 range) instead of flat +10 per entity extraction
- Recall fetches `limit * 2` candidates in progressive mode for better overflow quality
- `archived: bool` field on `MemoryEntry` for tracking compressed memories
- `consolidation_interval: int` field on `MemorySettings` (default 20)
- `interaction_count: int` field on `SoulConfig` for persistence

---

## [0.2.8] -- 2026-03-27

### Added
- `soul health` CLI — audit memory tiers, duplicates, orphan nodes, bond sanity
- `soul cleanup` CLI — remove dupes, stale evals, orphans (--dry-run, --auto)
- `soul repair` CLI — reset energy/bond, rebuild graph, clear evals/skills
- `soul_skills`, `soul_evaluate`, `soul_learn`, `soul_evolve`, `soul_bond` MCP tools (23 total)
- `soul recall --full` flag for complete memory content (no truncation)
- `soul recall --json` flag for machine-readable output
- `soul_forget`, `soul_edit_core`, `soul_health`, `soul_cleanup` MCP tools
- Biorhythms documentation with always-on vs companion usage guide
- Always-On Worker preset in configuration docs

### Changed
- Default biorhythms now always-on (energy_drain_rate=0, social_drain_rate=0, tired_threshold=0)
- Companion souls opt-in to drain via explicit biorhythm config

### Fixed
- Evolution pending mutations now persist across save/reload cycles
- Previously, proposed mutations were lost on export/awaken (in-memory only)

---

## [0.2.7] — 2026-03-26

### Fixed

- **Bond system** — `context_for()` now passes actual `bond_strength` to memory recall instead of always defaulting to 100.0. Bond score now genuinely influences which memories surface in context.
- **Evolution pipeline** — `observe()` now calls `evaluate()` to build evaluation history. Previously, evaluation history was always empty so evolution triggers never fired and OCEAN personality was stuck at defaults forever.
- **Entity extraction** — added topic extraction patterns for natural speech (`"I work on X"`, `"I'm a Y"`, `"we're building Z"`). Captures concepts from real conversations that lack capitalized proper nouns or hardcoded tech names. Regex bounded to 5 words with trailing stop-word trimming.
- **Heuristic evaluator calibration** — recalibrated scoring functions so solid technical conversations score ~0.65–0.80 instead of ~0.33. Completeness threshold lowered to 20 words, relevance uses user tokens as denominator, specificity counts 6+ char words. Evolution trigger thresholds adjusted to 0.55 for heuristic mode.

### Added

- **Skills persistence** — `SkillRegistry` now serialized in `SoulConfig` and restored on `awaken()`. Learned skills survive export/import cycles.
- **Evaluation history persistence** — `Evaluator._history` now serialized in `SoulConfig` and restored on `awaken()`. Evaluation streaks accumulate across sessions.
- **18 real-world e2e tests** — new `test_e2e_real_world.py` with 8 scenarios simulating realistic multi-turn human conversations: developer onboarding, personal bonding, evolution triggers, self-model emergence, bond-filtered recall, full lifecycle persistence, mixed conversation, and evolution mutation proposals. (#143)

---

## [0.2.6] — 2026-03-24

### Added

- **MCP LCM context tools** — 5 new MCP tools expose Lossless Context Management through the soul server: `soul_context_ingest`, `soul_context_assemble`, `soul_context_grep`, `soul_context_expand`, `soul_context_describe`. Per-soul in-memory SQLite stores, CognitiveEngine auto-wired to compactors. (#138)
- **CLI runtime parity** — 13 new CLI commands for full feature parity with the Python API: `observe`, `reflect`, `feel`, `prompt`, `forget`, `edit-core`, `evolve`, `evaluate`, `learn`, `skills`, `bond`, `events`, `context`. Total: 34 commands. (#138)
- **Soul directory auto-detect** — MCP server now auto-detects `.soul/` in the working directory or `~/.soul/` when no `SOUL_DIR`/`SOUL_PATH` env var is set. Uses `Path.cwd()` for all install modes. Logs empty directory fallthrough. (#136)
- **Docs refresh** — updated getting-started, cognitive-engine, integrations, and memory-architecture guides for v0.2.5 features. (#137)

### Fixed

- **Dedup containment coefficient** — enriched facts (where a short fact is a subset of a longer version) now correctly land in MERGE range instead of CREATE. Containment coefficient (`intersection / min-set * 0.75`) used as floor for Jaccard, with `min_size >= 3` guard against spurious matches. (#135)
- **CI dependency resolution** — `dspy` and `litellm` extras emptied to prevent `uv sync` from failing on unresolvable transitive dependencies. Both can still be installed manually. (#136)
- **MCP test isolation** — autouse fixture now monkeypatches CWD and `Path.home()` to prevent auto-detect from loading real souls during tests. (#136)

---

## [0.2.5] — 2026-03-23

### Added

- **Cognitive adapters** — wire any LLM into a soul's cognitive engine without subclassing. Pass `engine="auto"` to auto-detect from installed packages, `engine=AnthropicEngine()` / `OpenAIEngine()` / `OllamaEngine()` / `LiteLLMEngine("ollama/llama3.2")` for explicit control, or any async callable `engine=my_fn`. New install extras: `[anthropic]`, `[openai]`, `[ollama]`, `[litellm]`, `[llm]` (all three at once).
- **MCP sampling engine** — when the soul runs as an MCP server inside Claude Code or Claude Desktop, it now delegates cognitive tasks (significance gating, fact extraction, reflection) to the host LLM via `ctx.sample()`. No separate API key or extra dependency required.
- **Real embedding providers** — `SentenceTransformerEmbedder`, `OpenAIEmbedder`, and `OllamaEmbedder` replace hash-based similarity for semantic memory search. Install with `[embeddings-st]`, `[embeddings-openai]`, or `[embeddings-ollama]`.
- **Lossless Context Management (LCM)** — conversation context is never silently dropped. Three-level compaction (Summary → Bullets → Truncate) with a SQLite-backed conversation store and a hierarchical DAG for full-fidelity retrieval. Zero new dependencies — sqlite3 is stdlib.
- **Memory visibility tiers** — every `MemoryEntry` now carries a `visibility` field: `PUBLIC`, `BONDED`, or `PRIVATE`. Recall is automatically filtered by requester identity and bond strength.
- **Soul templates and `SoulFactory`** — define soul archetypes once, stamp out multiple souls in a single call. Useful for simulations, multi-agent pipelines, and testing.
- **A2A Agent Card bridge** — bidirectional conversion between Google A2A Agent Cards and `.soul` files. New CLI commands: `soul export-a2a` and `soul import-a2a`.
- **Format importers** — `SoulSpecImporter` reads SOUL.md / soul.json persona files; `TavernAIImporter` reads Character Card V2 (JSON and PNG with embedded `chara` tEXt chunk). No Pillow dependency for PNG imports.
- **Graph traversal** — `KnowledgeGraph` gains `traverse()`, `shortest_path()`, `get_neighborhood()`, `subgraph()`, and `progressive_context()` (L0/L1/L2 progressive loading for token-budget-aware context injection).
- **Learning events** — `LearningEvent` spec model wired into `Soul.learn()` for structured skill acquisition tracking alongside the existing XP system.
- **Multi-participant Interaction** — `Interaction` generalises to N participants. `user_input` and `agent_output` remain as backward-compatible properties. `Identity.bonds` replaces deprecated `bonded_to` with a `list[BondTarget]` and auto-migration.
- **Multi-soul coordination spec** (DSP v0.5.0 draft) — defines the Tuckman-informed lifecycle, transitive trust decay, reputation scoring, and handoff protocol for soul-to-soul collaboration across agents and platforms.

### Fixed

- Contradiction detection now runs during `observe()` on every call — location and employer changes correctly supersede stale facts rather than accumulating as duplicates.
- Third-person relationship extraction: `"Sarah's manager is Dave"` now produces a directed knowledge graph edge rather than being silently dropped.
- Verb-based contradiction patterns: `"lives in NYC"` is correctly superseded by `"moved to Amsterdam"` across sessions.
- Dedup tokenizer now preserves 2-character tokens (`go`, `js`, `ai`, `ml`) — fixes false-positive deduplication of short tech terms that were previously collapsed.
- `progressive_context()` renamed from the conflicting `format_context()` in the graph module — removes import collision with the runtime's own `format_context`.

### Changed

- `Soul.birth()`, `Soul.awaken()`, and `Soul.birth_from_config()` now accept an `engine` keyword argument (`CognitiveEngine | Callable | Literal["auto"] | None`). Passing a bare callable is automatically wrapped; `"auto"` resolves the best available adapter from installed packages.
- `Identity.bonded_to` is deprecated in favour of `bonds: list[BondTarget]`. Existing `.soul` files round-trip cleanly via auto-migration.

---

## [0.2.4] — 2026-03-19

- Version bump, whitepaper update (reincarnation and archival memory working).
- Rubric-based self-evaluation for skills and learning events.
- Community fix: dedup tokenizer short-token false positives (PR #109).

---

## [0.2.3] — 2026-03-05

- Initial public release on GitHub.
- 1,189 tests, spec + runtime two-layer architecture.
- MCP server (12 tools, 3 resources), 15-command CLI.
- Empirical validation: 20/20 multi-judge benchmark, head-to-head vs. Mem0.
- Soul Health Score framework (7 dimensions, SHS 90.2/100).
