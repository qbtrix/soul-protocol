<!-- New file (2026-04-29) — RFC for the v0.5.0 memory update primitive set:
     six new operations (confirm, update, supersede, forget, purge, reinstate)
     gated by a prediction-error score and a reconsolidation window. Captures
     the schema additions (retrieval_weight, supersedes back-edge,
     prediction_error), recall changes (weight filter + provenance), trust
     chain hooks, CLI/MCP surface, a 2-3 hour spike scope, open questions for
     captain review, the 0.4 → 0.5 migration walkthrough, the spec-doc
     stanzas that need follow-up, and the cog-sci references behind the
     design. Pairs with issue #192. -->

# RFC: Memory update primitives (confirm / update / supersede / forget / purge / reinstate)

| Field | Value |
|---|---|
| Status | Draft |
| Date | 2026-04-29 |
| Authors | OCEAN team |
| Target version | 0.5.0 |
| Related | issue #192, PR #193 (precursor — supersede + forget --id) |

## 1. Summary

This RFC adds six runtime memory operations to Soul Protocol so callers can correct, refresh, suppress, or restore memories with the same vocabulary the brain uses. Three update verbs (`confirm`, `update`, `supersede`) are gated by a prediction-error score and a reconsolidation window. Two destructive verbs replace today's single `forget`: `forget` becomes a non-destructive retrieval-weight decay, and `purge` becomes the explicit "delete with backup" path. A new `reinstate` lifts a forgotten memory back into recall. Recall surfaces a provenance chain so callers can see the supersession history of any returned entry. The wire format gains three fields on `MemoryEntry` and a per-soul reconsolidation map.

## 2. Motivation

### Today's gap

The runtime already sets `superseded_by` internally during dream-cycle dedup (`dream._dedup_semantic`) and contradiction resolution (`manager._resolve_fact_conflicts`). PR #193 exposed that path to callers via `Soul.supersede(old_id, new_content, reason=...)`, plus surgical single-id deletion via `Soul.forget_one`. That covers half the story.

The other half is missing:

- No way to say "I just confirmed this fact is still right." The only operation that touches activation today is recall itself.
- No way to update an entry in place inside a short post-recall window. Every change writes a new row even when the change is small.
- No way to suppress an entry without deleting it. Today's `Soul.forget(query)` is a hard delete.
- No way to lift a forgotten entry back into recall. Once you delete it, it's gone (modulo `.soul.bak`).
- No score on the change that distinguishes "minor revision" from "this was wrong, write a new orthogonal trace."

### Cog-sci grounding

Six findings shape the design:

- **Reconsolidation** (Nader, Schafe & LeDoux 2000). Retrieving a memory briefly destabilizes it. Inside that window the trace is editable; outside it, the trace is stable and edits must write a new chunk.
- **Prediction-error gating** (Sevenster, Beckers & Kindt 2014). Zero PE leaves the trace alone. Moderate PE opens reconsolidation. High PE bypasses it and writes a new orthogonal trace.
- **Schema fast-tracking** (Tse et al. 2007). Schema-consistent updates consolidate quickly; schema-conflicting ones force a new trace.
- **Retrieval-induced inhibition** (Bjork & Bjork 1992; Wimber et al. 2015). Forgetting is retrieval-strength suppression, not storage erasure. Spontaneous recovery is real.
- **Continued influence** (Brashier et al. 2021). Old beliefs regress when the correction is hard to retrieve. Source links matter.
- **ACT-R declarative chunks** (Anderson et al. 2004). Chunks are immutable; updates are new chunks plus activation competition. The runtime already borrows ACT-R activation; this RFC extends it.

### User story

Prakash recalls "Project Atlas ships in May." He realizes the date moved to July. Today:

```python
# Today (0.4.x) — write a new memory, hope it ranks higher, or supersede explicitly.
new_id = await soul.remember("Project Atlas ships in July")
# Or:
result = await soul.supersede(old_id, "Project Atlas ships in July", reason="date slipped")
```

After this RFC:

```python
# Just-recalled, low PE — refresh and walk away.
await soul.confirm(memory_id)

# Just-recalled, moderate PE, still inside the reconsolidation window.
await soul.update(memory_id, patch="ships in July, not May", prediction_error=0.4)

# Outside the window or high PE — supersede stays, with a PE score attached.
await soul.supersede(memory_id, "Project Atlas ships in July", reason="date slipped", prediction_error=0.7)
```

The CLI gets the same vocabulary: `soul confirm`, `soul update`, `soul supersede`, `soul forget`, `soul purge`, `soul reinstate`.

## 3. Proposed model

The full surface is six methods on `Soul`. Each is described below with signature, semantics, when prediction-error gating fires, side effects, and error cases.

### 3.1 `confirm`

```python
async def confirm(
    self,
    memory_id: str,
    *,
    prediction_error: float = 0.0,
) -> dict:
    ...
```

**Semantics.** Refresh activation and recency on a memory the caller has just verified. Adds the current time to `access_timestamps`, increments `access_count`, leaves content untouched, and bumps `retrieval_weight` back toward 1.0 if it has decayed. No new memory is written.

**PE gating.** Only fires when `prediction_error < 0.2` (default 0.0). Higher values raise `ValueError`; the caller should switch to `update` or `supersede`. The 0.2 boundary is configurable via `MemorySettings.confirm_pe_max` (default 0.2).

**Side effects.** Appends a `memory.confirm` entry to the trust chain with `{id, layer, weight_before, weight_after}`. No supersede audit trail entry.

**Errors.**

| Case | Behavior |
|---|---|
| `memory_id` not found | Returns `{"found": False}`, no chain entry. |
| `memory_id` is superseded (has `superseded_by`) | Raises `MemorySupersededError`; caller should confirm the active entry instead. |
| `prediction_error` outside `[0.0, 1.0]` | Raises `ValueError`. |
| `prediction_error >= 0.2` | Raises `ValueError("PE too high for confirm — use update or supersede")`. |

### 3.2 `update`

```python
async def update(
    self,
    memory_id: str,
    *,
    patch: str,
    prediction_error: float = 0.5,
    reason: str | None = None,
) -> dict:
    ...
```

**Semantics.** In-place edit within the reconsolidation window. The window opens on the most recent `recall()` that returned this memory id. If the window is open and `prediction_error < 0.85`, `content` is replaced with `patch`, `last_accessed` and `access_timestamps` are refreshed, and `retrieval_weight` resets to 1.0. The original content is preserved on disk in a per-entry `revisions` list (added in 0.5.0) so the in-place update is reversible.

**PE gating.** `0.2 <= PE < 0.85` is the valid range. PE outside the window forces a different primitive:

| PE range | Primitive |
|---|---|
| `< 0.2` | `confirm` |
| `0.2 <= PE < 0.85` | `update` (window must be open) |
| `>= 0.85` | `supersede` (forced) |

When the window is closed, `update` raises `ReconsolidationWindowClosedError` and the caller must promote to `supersede`.

**Side effects.** Appends a `memory.update` chain entry with `{id, layer, prediction_error, patch_hash, revision_index}`. The `patch_hash` lets verifiers re-derive what changed without reading the soul archive.

**Errors.**

| Case | Behavior |
|---|---|
| `memory_id` not found | `{"found": False}`. |
| `memory_id` is superseded | `MemorySupersededError`. |
| Reconsolidation window closed | `ReconsolidationWindowClosedError` with `closed_at` timestamp. |
| `prediction_error >= 0.85` | `ValueError("PE too high for update — use supersede")`. |
| Empty `patch` | `ValueError`. |

### 3.3 `supersede` (extends 0.4.0)

```python
async def supersede(
    self,
    old_id: str,
    new_content: str,
    *,
    reason: str | None = None,
    prediction_error: float = 0.5,
    importance: int = 5,
    memory_type: MemoryType | None = None,
    emotion: str | None = None,
    entities: list[str] | None = None,
) -> dict:
    ...
```

**Semantics.** Same as 0.4.0 with one addition: the new entry records the `prediction_error` score in a new `prediction_error` field, and the old entry gains a `supersedes` back-edge so the pair links both ways. Recall returns the new entry by default and exposes the chain via the new provenance field.

**PE gating.** `supersede` accepts any PE in `[0.0, 1.0]`. PE under 0.2 is allowed but emits a soft warning ("supersede with low PE — did you mean confirm?"). PE >= 0.85 is the recommended path; lower PE is fine but signals the caller may be over-using supersede where update would suffice.

**Side effects.** Same `memory.supersede` chain entry as 0.4.0, with `prediction_error` added to the payload. `supersede_audit` trail entry unchanged.

**Errors.** Unchanged from 0.4.0 (`found=False` on missing `old_id`).

### 3.4 `forget` (semantics shift in 0.5.0)

```python
async def forget(
    self,
    memory_id: str | None = None,
    *,
    query: str | None = None,
    weight_target: float = 0.0,
) -> dict:
    ...
```

**Semantics.** **Breaking change from 0.4.0.** `forget` no longer deletes. It drops the entry's `retrieval_weight` to `weight_target` (default 0.0). The entry stays on disk and remains accessible via `Soul.facts(include_forgotten=True)` and `soul recall --include-forgotten`. Recall filters entries with `retrieval_weight < 0.1` by default (see §6).

The single-id form is the recommended path. The query form (`forget(query="...")`) is preserved for back-compat and decays every match — it does **not** delete. To delete, use `purge` (§3.5).

**PE gating.** Not gated. Forgetting is a caller intent, not an inference.

**Side effects.** Appends a `memory.forget` chain entry with `{id, layer, weight_before, weight_after, query}`. Note: the action name is unchanged from 0.4.0 (`memory.forget`), but the payload shape grows. Verifiers reading old chains see only `{id, tier}`; new chains see weight fields too.

**Errors.**

| Case | Behavior |
|---|---|
| Neither `memory_id` nor `query` given | `ValueError`. |
| Both given | `ValueError`. |
| `memory_id` not found | `{"found": False, "decayed": 0}`. |

### 3.5 `purge` (new in 0.5.0)

```python
async def purge(
    self,
    memory_id: str | None = None,
    *,
    query: str | None = None,
    apply: bool = False,
) -> dict:
    ...
```

**Semantics.** Hard delete with `.soul.bak` backup. Reserved for GDPR / safety / privacy obligations. Defaults to dry-run preview (`apply=False`) — same gate as 0.4.0's `soul forget --apply`. This is the only operation in the new set that actually destroys data.

**PE gating.** Not gated.

**Side effects.** Writes a `.soul.bak` backup before deletion. Appends a `memory.purge` chain entry with `{id, layer, payload_hash, deleted_at}`. The `payload_hash` is a SHA-256 of the deleted entry's content, so verifiers can confirm "this entry once existed and was deleted" without storing the content itself.

**Errors.**

| Case | Behavior |
|---|---|
| `apply=False` | Preview only. Returns `{"would_delete": [...], "count": N}`. |
| `memory_id` not found | `{"found": False, "deleted": 0}`. |
| Backup write fails | Raises `BackupError`, no deletion happens. |

### 3.6 `reinstate`

```python
async def reinstate(
    self,
    memory_id: str,
    *,
    weight: float = 1.0,
) -> dict:
    ...
```

**Semantics.** Restore a forgotten entry's `retrieval_weight` to `weight` (default 1.0). The entry must still exist on disk — this is the inverse of `forget`, not the inverse of `purge`. Reinstate after purge is impossible; the caller must restore from `.soul.bak`.

**PE gating.** Not gated.

**Side effects.** Appends a `memory.reinstate` chain entry with `{id, layer, weight_before, weight_after}`.

**Errors.**

| Case | Behavior |
|---|---|
| `memory_id` not found | `{"found": False}`. |
| `weight` outside `[0.0, 1.0]` | `ValueError`. |

## 4. Schema additions

Three new fields on `MemoryEntry` and one new per-soul map.

### 4.1 New fields

```python
class MemoryEntry(BaseModel):
    # ... existing 0.4.0 fields ...

    # 0.5.0 additions
    retrieval_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    supersedes: str | None = None
    prediction_error: float | None = Field(default=None, ge=0.0, le=1.0)
    revisions: list[dict] = Field(default_factory=list)  # [{content, replaced_at, patch_hash}]
```

| Field | Default | Role |
|---|---|---|
| `retrieval_weight` | `1.0` | Gates recall. `forget` drops it; `reinstate` restores it. Recall filter default: `>= 0.1`. |
| `supersedes` | `None` | Inverse of `superseded_by`. The pair fall out as a back-edge graph for provenance walks. |
| `prediction_error` | `None` | The PE score when the entry was created via `supersede`. Unset for `remember`/`observe`-created entries. |
| `revisions` | `[]` | History of in-place updates. Empty for entries that have never been `update`-d. |

### 4.2 Reconsolidation map

A per-soul, in-memory map keyed by entry id with TTL:

```python
class ReconsolidationMap:
    """Per-soul map of {entry_id: window_opens_at}."""

    def open(self, entry_id: str, ttl_seconds: float = 3600.0) -> None: ...
    def is_open(self, entry_id: str) -> bool: ...
    def close(self, entry_id: str) -> None: ...
```

**Why a map and not a per-soul timestamp?** A single timestamp can only track one open window. A map lets multiple recalls open independent windows — closer to how the brain handles parallel reactivations of different traces. It's also cheap: the map is in-memory only (not persisted), bounded by cleanup of expired entries on every `update` call, and capped at 1000 entries (LRU eviction).

**TTL default.** 1 hour (3600 seconds). Configurable via `MemorySettings.reconsolidation_window_seconds`. See §11 for the open question on the right default.

**When windows open.** Every successful `recall()` that returns an entry calls `reconsolidation_map.open(entry.id)`. Every `update`, `supersede`, or `forget` on an entry calls `close()` to invalidate the window.

**Persistence.** Not persisted to `.soul`. On awaken, all windows start closed. Rationale: the window models cellular destabilization, which has no offline counterpart. A soul that hasn't been recalled-against in a session should not have stale write windows lingering.

### 4.3 Migration story (0.4.x → 0.5.0)

| Field | Migration |
|---|---|
| `retrieval_weight` | Backfill `1.0` for every entry. |
| `supersedes` | Derive from existing `superseded_by` reverse mapping. For every entry A where `A.superseded_by = B`, set `B.supersedes = A.id`. |
| `prediction_error` | Leave `None` for legacy entries. |
| `revisions` | Empty list. |

The migration is idempotent. Re-running `soul migrate` on an already-migrated soul is a no-op. See §12 for the walkthrough.

## 5. Recall changes

`recall()` gains two behaviors:

### 5.1 Weight filter

Default behavior: skip entries with `retrieval_weight < 0.1`. Configurable per call:

```python
results = await soul.recall(
    "project atlas",
    min_retrieval_weight=0.1,    # default
    include_forgotten=False,      # set True to bypass the weight filter
)
```

Entries with `superseded_by != None` are still filtered (existing 0.4.x behavior preserved).

### 5.2 Provenance

Recall returns each entry with a `provenance` field:

```python
[
    {
        "type": "supersedes",
        "target_id": "abc123",
        "reason": "date slipped",
        "prediction_error": 0.7,
        "timestamp": "2026-04-29T14:00:00Z",
    },
    # ... older links walked back via the .supersedes chain
]
```

The chain is built by walking the `supersedes` back-edge. **Spike-version constraint:** the spike returns only the immediate parent (one hop). Production version walks the full chain.

Existing recall callers that don't read `provenance` are unaffected — the field is additive on the return shape.

## 6. Trust chain hooks

| Action | Payload | When emitted |
|---|---|---|
| `memory.confirm` | `{id, layer, weight_before, weight_after}` | Every successful `confirm`. |
| `memory.update` | `{id, layer, prediction_error, patch_hash, revision_index}` | Every successful `update`. |
| `memory.supersede` | `{old_id, new_id, reason, prediction_error}` | Every successful `supersede` (extends 0.4.0). |
| `memory.forget` | `{id, layer, weight_before, weight_after, query?}` | Every successful `forget` (semantics shift). |
| `memory.purge` | `{id, layer, payload_hash, deleted_at}` | Every successful `purge` with `apply=True`. |
| `memory.reinstate` | `{id, layer, weight_before, weight_after}` | Every successful `reinstate`. |

`purge` is the only operation that actually destroys data. The rest are non-destructive and can be unwound by a sequence of inverse operations (forget → reinstate, update → write a new revision matching the old content, supersede → write a new entry with the old content as the new content).

The action namespace registry in `spec/journal.py` gains `memory.confirm`, `memory.update`, `memory.purge`, `memory.reinstate` alongside the existing `memory.forget` and `memory.supersede`. `memory.forgotten` (the older verb form) stays for back-compat reads.

## 7. CLI surface

| Command | Notes |
|---|---|
| `soul confirm <path> <id>` | New. Optional `--pe FLOAT`. Optional `--user` and `--domain` filter the resolution of `<id>` for namespace safety. |
| `soul update <path> <id> --patch <text>` | New. Optional `--pe FLOAT`, `--reason <text>`. |
| `soul supersede <path> <new_content> --old-id <id>` | Existing 0.4.0 command. Adds `--pe FLOAT`. |
| `soul forget <path> [QUERY] [--id <id>]` | Semantics shift. **No longer deletes.** Now decays `retrieval_weight`. Old `--apply` flag retained but means "actually decay" instead of "actually delete". |
| `soul purge <path> [QUERY] [--id <id>] --apply` | New. Hard delete with `.soul.bak`. Defaults to dry-run preview, requires `--apply` to commit. |
| `soul reinstate <path> <id>` | New. Optional `--weight FLOAT` (default 1.0). |

**Mutually exclusive flags:** `--id`, `QUERY`, `--entity`, `--before` are mutually exclusive on `forget` and `purge` (same policy as 0.4.0's `forget`).

**Identity flags (where they make sense):** `--user <user_id>` and `--domain <domain>` apply to all six commands. They scope the operation to memories owned by that user or sitting in that domain. A `confirm` against an id that exists outside the requested user/domain returns `{"found": False}`.

## 8. MCP surface

The same six primitives ship as MCP tools:

| MCP tool | Maps to |
|---|---|
| `soul_confirm` | `Soul.confirm` |
| `soul_update` | `Soul.update` |
| `soul_supersede` | `Soul.supersede` (already shipped) |
| `soul_forget` | `Soul.forget` (semantics shift) |
| `soul_purge` | `Soul.purge` |
| `soul_reinstate` | `Soul.reinstate` |

MCP-side argument schemas mirror the Python signatures with one addition: each tool accepts an optional `path` argument so multi-soul MCP servers can route the call. The MCP surface is **deferred** to stage 3 of v0.5.0 — see spike scope below.

## 9. Spike scope (stage 2 of v0.5.0)

The spike is a 2-3 hour agent-time build the captain runs locally for a few days before the full implementation lands. Its goal is daily-use validation of the API shape, not production readiness.

**Spike includes:**

- Six new `Soul.<method>()` API calls. Simplest possible implementations — no edge-case handling beyond raising on missing ids.
- `retrieval_weight` field on `MemoryEntry`. Runtime-only (not persisted across awaken yet).
- The five new CLI commands (six counting renamed `soul forget`).
- Recall with the `retrieval_weight < 0.1` filter applied by default.
- Provenance in recall output. Spike version returns the immediate parent only (one hop, no full chain walk).
- Trust chain hooks for all six actions.

**Spike defers:**

- Migration tool (`soul migrate 0.4 → 0.5`). Spike souls start fresh.
- Reconsolidation window. `update` always succeeds in the spike — no window check, no map.
- PE scoring logic. PE defaults to `0.5` everywhere; the captain feels out PE-as-a-knob in daily use before the production version derives it from a real signal.
- MCP surface.
- Comprehensive tests. Smoke tests only.
- Full docs. CHANGELOG entry only; full `cli-reference.md` and `api-reference.md` updates land with production.

## 10. Open questions

These are decisions where multiple defaults are defensible. Captain weighs in before the spike starts.

1. **Reconsolidation window default.** 1 hour, 4 hours, or all-day? 1 hour mirrors the lab-rat reconsolidation window. 4 hours fits a typical work session. All-day matches "everything I touched today is editable." The RFC defaults to 1 hour but flags this as the most user-visible knob.

2. **PE thresholds.** Is `0.2 / 0.85` the right split for `confirm` vs `update` vs `supersede`? PE here is a caller-supplied number; we don't yet have an LLM-based PE estimator. The thresholds matter only for the hard error gates (PE >= 0.85 forces supersede). Captain may want softer warnings instead of errors.

3. **Retrieval-weight floor.** Default filter cutoff: `0.1`. Should the floor be `0.01` (more permissive — forgotten entries still surface in deep recalls), `0.1` (current proposal — clean separation), or exactly `0` (only completely-zeroed entries are filtered)?

4. **Forget chain entry every time.** Every `forget` emits a `memory.forget` chain entry. For a soul where the user runs daily forgets ("the conversation was noise"), this floods the trust chain. Should low-weight forgets (e.g. weight already < 0.1) skip the chain entry? RFC currently says no — every forget emits — for audit-trail completeness.

5. **Backward-compat for `Soul.forget(query)`.** Three options:
   - **Keep, semantics shift.** `forget(query)` now decays every match, doesn't delete. RFC currently picks this.
   - **Deprecate, emit warning.** Same as above plus a `DeprecationWarning` for one minor version, removed in 0.6.
   - **Remove, force `purge(query)`.** Breaking change — query-form callers must explicitly pick decay or delete.

   The RFC picks option 1 because option 3 forces every existing caller to read this changelog and option 2 is just option 1 with extra noise.

## 11. Migration walkthrough (0.4.x → 0.5.0)

```
$ soul migrate ~/.soul/aria.soul --to 0.5.0

Inspecting aria.soul (current version: 0.4.0)
  episodic entries: 2,341
  semantic entries: 1,008
  procedural entries: 12
  social entries: 47

Backing up to aria.soul.bak.0.4.0
Migration plan:
  - Backfill retrieval_weight=1.0 on 3,408 entries
  - Derive supersedes back-edge from existing superseded_by (218 pairs found)
  - Leave prediction_error=None on legacy entries
  - Initialize empty revisions list per entry
  - Update format version to 0.5.0

Apply? [y/N]: y

Done. aria.soul migrated to 0.5.0 (3.2s).
Backup retained at aria.soul.bak.0.4.0.
```

The migration is idempotent. Re-running on a 0.5.0 soul is a no-op: the version check short-circuits.

The migration tool ships as `soul migrate`, gated by an explicit `--to 0.5.0` flag so users can't auto-upgrade by mistake. A `--dry-run` flag prints the plan without applying.

## 12. Conformance impact on docs/SPEC.md

The following stanzas need updates in a follow-up PR (not this RFC):

| Stanza | Change |
|---|---|
| §4.2 (`MemoryEntry`) | Add `retrieval_weight`, `supersedes`, `prediction_error`, `revisions` fields. Note that pre-0.5.0 readers must accept missing fields with the documented defaults. |
| §4.4 (Recall contract) | Add `min_retrieval_weight` and `include_forgotten` parameters. Add `provenance` to the return shape. |
| New §4.5 (Update contract) | Document `confirm`, `update`, `supersede`, `forget`, `purge`, `reinstate` semantics at the spec level — language-agnostic, like the existing recall contract. |
| §10A.1 (`TrustEntry`) catalog | Add `memory.confirm`, `memory.update`, `memory.purge`, `memory.reinstate` to the catalog. |
| §11 (Conformance) | Add a row for the update primitives — implementations conforming to 0.5.0 must support all six. |

The architect's v0.5.0 SPEC update PR scopes these changes; this RFC does not modify SPEC.md directly.

## 13. References

- Anderson, J. R., Bothell, D., Byrne, M. D., Douglass, S., Lebiere, C., & Qin, Y. (2004). An integrated theory of the mind. *Psychological Review*, 111(4), 1036-1060. doi:10.1037/0033-295X.111.4.1036
- Bjork, R. A., & Bjork, E. L. (1992). A new theory of disuse and an old theory of stimulus fluctuation. In A. Healy, S. Kosslyn, & R. Shiffrin (Eds.), *From learning processes to cognitive processes* (Vol. 2, pp. 35-67). Erlbaum.
- Brashier, N. M., Pennycook, G., Berinsky, A. J., & Rand, D. G. (2021). Timing matters when correcting fake news. *Proceedings of the National Academy of Sciences*, 118(5). doi:10.1073/pnas.2020043118
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval. *Nature*, 406(6797), 722-726. doi:10.1038/35021052
- Sevenster, D., Beckers, T., & Kindt, M. (2014). Prediction error demarcates the transition from retrieval to reconsolidation to new learning. *Learning & Memory*, 21(11), 580-584. doi:10.1101/lm.035493.114
- Tse, D., Langston, R. F., Kakeyama, M., Bethus, I., Spooner, P. A., Wood, E. R., Witter, M. P., & Morris, R. G. M. (2007). Schemas and memory consolidation. *Science*, 316(5821), 76-82. doi:10.1126/science.1135935
- Wimber, M., Alink, A., Charest, I., Kriegeskorte, N., & Anderson, M. C. (2015). Retrieval induces adaptive forgetting of competing memories via cortical pattern suppression. *Nature Neuroscience*, 18(4), 582-589. doi:10.1038/nn.3973
