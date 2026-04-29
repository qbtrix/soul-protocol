---
{
  "title": "Test Suite: Scope Tags and Hierarchical Memory Access Control",
  "summary": "Tests the `match_scope` and `match_scope_strict` helpers that implement hierarchical RBAC/ABAC filtering for memory recall. The suite covers bidirectional glob containment, strict one-way matching, scope normalization, export/awaken round-trips for scoped memories, and `Soul.recall` scope-filter integration.",
  "concepts": [
    "match_scope",
    "match_scope_strict",
    "scope tags",
    "RBAC",
    "ABAC",
    "glob pattern",
    "normalise_scopes",
    "bidirectional containment",
    "MemoryEntry scope",
    "Soul.recall filter",
    "segment boundary",
    "hierarchical access control"
  ],
  "categories": [
    "testing",
    "access control",
    "memory filtering",
    "security",
    "test"
  ],
  "source_docs": [
    "8dec6886601c51f6"
  ],
  "backlinks": null,
  "word_count": 467,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Scope tags are how Soul Protocol enforces that certain memories are only visible to callers with the right organizational context. A memory tagged `org:sales:leads` should not be visible to a caller with only `org:finance:*` access. This test file locks the `match_scope` semantics, which changed significantly in v0.3.1 from one-directional to bidirectional containment.

## match_scope: Bidirectional Containment

The key design decision is that `match_scope` is bidirectional: a caller scope is granted access if either:
- The caller's scope is contained within the memory's scope (narrow caller, broad memory), or
- The memory's scope is contained within the caller's scope (narrow memory, broad caller)

This enables two real-world patterns:

```python
# Bundled-archetype use case: caller with concrete scope sees glob-tagged memory
assert match_scope(["org:sales:leads"], ["org:sales:*"])

# Broad caller sees narrow memory
assert match_scope(["org:sales:*"], ["org:sales:leads"])
```

Critical boundaries:
- **Star wildcard**: `["*"]` matches everything
- **Segment boundary**: `"org:sales:*"` does NOT match `"org:salesforce"` — the wildcard only replaces full colon-delimited segments
- **Empty entity scopes**: Memories with no scope tags are visible to everyone (pre-scope memories stay accessible)
- **Empty allowed scopes**: A caller without a scope filter sees everything
- **Sibling subtrees**: `"org:sales:*"` does not match `"org:finance:*"` — no cross-tree leakage

## match_scope_strict: One-Directional Variant

`match_scope_strict` preserves the pre-v0.3.1 behavior where only the caller's scope is checked against the entity's scope (not the reverse). This is available for callers that genuinely require asymmetric enforcement:

```python
# strict: caller org:finance:reports does NOT match entity org:sales:*
assert not match_scope_strict(["org:finance:reports"], ["org:sales:*"])
```

Having both variants tested prevents accidental reversion — if the bidirectional logic is broken back to strict, the `TestMatchScope` tests catch it.

## normalise_scopes

Before any scope comparison, tags are normalized: lowercased, stripped of whitespace, deduplicated, and empty/non-string entries dropped. Tests verify:
- Mixed case is lowercased
- Leading/trailing spaces are removed
- Duplicate tags collapse to one
- Non-string values (integers, None) are silently dropped

This normalization exists because scope tags can come from user input or YAML configs where case and whitespace are inconsistent.

## MemoryEntry Shape Preservation

A separate test class verifies that `MemoryEntry` objects with scope tags survive export → awaken round-trips intact. Without this, scope tags could be silently dropped during serialization, leaving memories unprotected after a `.soul` file is loaded.

## Soul.recall Integration

The integration tests verify that `Soul.recall("x", allowed_scopes=["org:sales:*"])` actually filters the result set — memories without matching scopes do not appear in results. This end-to-end path tests that `match_scope` is actually called inside the recall pipeline, not just as a standalone helper.

## Known Gaps

No TODO or FIXME markers are present. The `test_glob_does_not_cross_segment_boundary` comment notes that `"org:sales*"` is "NOT a valid glob" — but the test only asserts the match fails; there is no test that an invalid glob pattern raises a warning or error rather than silently failing to match.