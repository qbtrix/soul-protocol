---
{
  "title": "Scope Matching — Bidirectional Hierarchical RBAC/ABAC Scope Evaluation",
  "summary": "This module provides `match_scope`, `match_scope_strict`, and `normalise_scopes` — pure-stdlib functions for evaluating hierarchical scope tags used across all Soul Protocol retrieval paths. The `match_scope` function uses bidirectional containment after a bug was found where agents with concrete scopes (`org:sales:leads`) could not see memories tagged with parent glob scopes (`org:sales:*`) from bundled archetypes.",
  "concepts": [
    "match_scope",
    "match_scope_strict",
    "normalise_scopes",
    "scope tags",
    "RBAC",
    "ABAC",
    "hierarchical glob",
    "bidirectional containment",
    "_contains",
    "scope matching",
    "org:sales:*",
    "memory visibility"
  ],
  "categories": [
    "scope",
    "access control",
    "spec layer",
    "retrieval filtering"
  ],
  "source_docs": [
    "51907b46bb282002"
  ],
  "backlinks": null,
  "word_count": 494,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Scope tags are Soul Protocol's RBAC/ABAC mechanism. Every memory entry, retrieval source, and journal event carries scope tags. When an agent recalls memories, the retrieval layer filters results to those whose scopes overlap with the agent's current scopes. A consistent, centralized implementation prevents subtle divergences between soul recall, fabric queries, kb retrievals, and pocket visibility checks.

## The Bidirectionality Fix

The original `match_scope` was unidirectional: it only checked whether the caller's `allowed_scopes` granted an entity's `entity_scopes`. This caused a real bug:

- A bundled archetype declares `default_scope: ["org:sales:*"]` on its core memories
- An agent installed from the archetype gets a concrete caller scope: `"org:sales:leads"`
- `match_scope(entity_scopes=["org:sales:*"], allowed_scopes=["org:sales:leads"])` returned `False`
- The agent could not see its own core memories

The fix: match returns `True` when containment holds **in either direction**:

```python
def match_scope(entity_scopes, allowed_scopes) -> bool:
    return any(
        _contains(entity, allowed) or _contains(allowed, entity)
        for entity in entity_scopes
        for allowed in allowed_scopes
    )
```

Now `_contains("org:sales:*", "org:sales:leads")` is `True` because the glob contains the concrete scope. And `_contains("org:sales:leads", "org:sales:*")` is also `True` in the reverse. Either direction produces a match.

## The `_contains` Helper

```python
def _contains(outer: str, inner: str) -> bool:
    if outer == "*": return True
    if outer == inner: return True
    if outer.endswith(":*"):
        prefix = outer[:-2]
        return inner == prefix or inner.startswith(prefix + ":")
    return False
```

Glob syntax is minimal: only `*` (match all) and `<prefix>:*` (match prefix and descendants). No regex, no nested wildcards. This is intentional — scope tags are namespaced ASCII identifiers, not filesystem paths, and complex glob patterns create security-review nightmares.

## `match_scope_strict`

The original unidirectional behavior is preserved for callers that genuinely need it — e.g., permission grant checks where "does the caller's scope explicitly cover this entity?" is the right question, not "does any relationship exist between the two scopes?".

## `normalise_scopes`

```python
def normalise_scopes(scopes) -> list[str]:
    # strip + lowercase + de-duplicate, preserve order
```

Scope tags are case-sensitive per the spec, but inputs from untrusted sources (user input, config files) may have inconsistent casing or trailing whitespace. `normalise_scopes` sanitizes inputs before they reach `match_scope`. Without this, `"Org:Sales:*"` and `"org:sales:*"` would be treated as different scopes.

## Empty-List Semantics

- Empty `entity_scopes` = "no scope assigned" → visible to any caller
- Empty `allowed_scopes` = "caller has no scope filter" → sees everything

This preserves backward compatibility: pre-scope memories (created before scope tagging was introduced) have empty scope lists and continue to surface in all retrieval results unchanged.

## Usage Pattern

```python
# In soul recall:
if not match_scope(entry.scope, caller_scopes):
    continue  # skip this memory

# In kb retrieval:
filtered = [a for a in articles if match_scope(a.scope, request.scopes)]
```

## Known Gaps

None. The module is intentionally minimal — no I/O, no imports beyond stdlib, no enums. The comment notes that `"*"` matches anything, but there is no explicit documentation of what happens with malformed scope strings (e.g., multiple consecutive colons). `normalise_scopes` strips and lowercases but does not validate structure.