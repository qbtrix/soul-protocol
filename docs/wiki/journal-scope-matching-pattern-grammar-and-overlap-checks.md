---
{
  "title": "Journal Scope Matching: Pattern Grammar and Overlap Checks",
  "summary": "Provides two public functions for colon-delimited scope pattern matching used throughout the journal engine, retrieval router, and credential broker. The module was extracted from the SQLite backend to make the shared logic accessible as a proper public API.",
  "concepts": [
    "scope matching",
    "wildcard patterns",
    "journal routing",
    "credential authorization",
    "colon-delimited scopes",
    "scope_matches",
    "scopes_overlap",
    "fanout",
    "segment grammar",
    "retrieval router",
    "credential broker"
  ],
  "categories": [
    "journal",
    "authorization",
    "routing",
    "patterns"
  ],
  "source_docs": [
    "c9e81ba6f9f0830f"
  ],
  "backlinks": null,
  "word_count": 498,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why This Module Exists

Scope strings like `org:sales:leads` are the routing and access-control primitive in the journal engine. Multiple subsystems — the SQLite backend, the retrieval router, and the credential broker — all need to match these scopes. Initially the helper lived as a private function inside `sqlite.py`, which caused those other subsystems to reach into a private symbol. This module lifts it into a proper public home.

## Scope Grammar

Scopes are colon-delimited segments. `*` wildcards exactly one segment — **not** a subtree:

| Pattern | Matches | Does Not Match |
|---|---|---|
| `org:sales` | `org:sales` | `org:sales:leads` |
| `org:sales:*` | `org:sales:leads`, `org:sales:deals` | `org:sales` |
| `org:*` | `org:sales`, `org:hr` | `org` |
| `org:*:leads` | `org:sales:leads`, `org:hr:leads` | `org:sales:deals` |

Segment count must match exactly. This is intentionally stricter than hierarchical containment — two scopes with different depths are different sets of events, not a parent-child relationship.

## `scope_matches` — Event Lookup

```python
def scope_matches(event_scopes: list[str], query_scopes: list[str]) -> bool:
```

Answers: "does this event belong to the set of events the query pattern names?"

Semantics are **asymmetric**: event scopes are concrete values written by producers; query scopes are patterns supplied by callers trying to retrieve events. Wildcards are meaningful on the query side; a wildcard in an event scope is unusual ("this event was published to a wildcard namespace").

The function iterates all (pattern, scope) pairs and returns `True` on the first match. Short-circuit evaluation means cheap cases exit fast.

## `scopes_overlap` — Credential Authorization

```python
def scopes_overlap(granted: list[str], requested: list[str]) -> bool:
```

Answers: "does the caller's credential cover what they are trying to access?"

This function is **symmetric** with respect to wildcards — either side may carry a `*`:

- A credential granted for `org:sales:*` authorizes a concrete request for `org:sales:leads`.
- A credential granted for `org:sales:leads` also authorizes a wildcard request for `org:sales:*` (an org-wide router that asserts "I operate anywhere in this subtree").

Both directions are deliberate. Breaking the first would mean broad credentials cannot be used for any concrete call. Breaking the second would prevent fanout routers from consuming per-scope credentials, crippling event distribution.

## Intentional Divergence from `spec.scope`

As of v0.3.1, `spec.scope.match_scope` implements hierarchical containment (a concrete scope matches its ancestor glob). The journal's `scope_matches` deliberately keeps the stricter segment-count grammar. The reason: the journal is answering set membership, not tree containment. Moving to containment semantics would change which events get fanned out to which subscribers, a behavioral regression.

## Data Flow

1. Producer appends an event with `scope=["org:sales:leads"]`.
2. Subscriber queries with `scope=["org:sales:*"]`.
3. `SQLiteJournalBackend.query()` fetches candidate rows, then calls `scope_matches(entry.scope, query_scopes)` to post-filter.
4. For auth checks, the broker calls `scopes_overlap(granted_scopes, requested_scopes)` before allowing access.

## Known Gaps

- This module is described as a placeholder until `spec.scope` (#162) lands. Once `spec.scope.match_scope` ships with full grammar, callers should migrate. The plan is same-name, same-shape swap.
- No regex or glob syntax beyond `*` — complex patterns like `org:**` (multi-segment wildcard) are not supported.