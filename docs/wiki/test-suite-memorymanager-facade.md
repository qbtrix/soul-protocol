---
{
  "title": "Test Suite: MemoryManager Facade",
  "summary": "Core test suite for the MemoryManager facade, covering all five memory stores (core, episodic, semantic, procedural, knowledge graph), cross-store recall, significance-gated observation, and the Bug #15 edit_core behavior fix.",
  "concepts": [
    "MemoryManager",
    "core memory",
    "episodic store",
    "semantic store",
    "procedural store",
    "knowledge graph",
    "cross-store recall",
    "significance gate",
    "edit_core",
    "Bug #15",
    "memory clear"
  ],
  "categories": [
    "memory",
    "testing",
    "facade",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "12b2e89745c0350b"
  ],
  "backlinks": null,
  "word_count": 545,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: MemoryManager Facade

`test_memory.py` is the primary integration test suite for `MemoryManager`, the unified façade that coordinates soul-protocol's five-tier memory architecture. Created 2026-02-22 and last updated 2026-03-06 (Bug #15 fix).

### Why MemoryManager Needs Its Own Test Suite

Each memory tier (core, episodic, semantic, procedural, knowledge graph) has independent storage semantics. The façade pattern means bugs can arise at the coordination layer — for instance, `recall()` must fan out to multiple stores without duplicating results, and `clear()` must reset the right stores without wiping persistent core memory. These tests guard that boundary.

### Core Memory: set_core / get_core / edit_core

```python
async def test_core_memory_set_and_get(manager):
    manager.set_core(persona="I am Aria, a helpful assistant.", human="")
    core = manager.get_core()
    assert core.persona == "I am Aria, a helpful assistant."
```

`set_core` uses `None` as a sentinel for "leave this field unchanged" — passing `persona=None` does not overwrite the existing persona. This prevents accidental blanking of identity fields when only one field needs updating.

**Bug #15 Fix** — `edit_core` previously appended to existing content, which caused persona drift over repeated edits. The fix changed the behavior to full replacement. `test_core_memory_edit` validates the new replace semantics explicitly.

### Episodic, Semantic, and Procedural Stores

Each store follows the same add/search pattern:

- `test_episodic_add_and_search` — adds an `Interaction` and confirms keyword search returns it
- `test_semantic_add_and_search` — adds a `MemoryEntry(type=SEMANTIC, ...)` and verifies retrieval
- `test_procedural_add_and_search` — same for procedural (how-to) memories

The parity between these three tests enforces interface consistency — all three stores must satisfy the same retrieval contract even though their internal data models differ.

### Cross-Store Recall

```python
async def test_recall_across_stores(manager):
    # recall() must surface entries from BOTH episodic and semantic
```

`recall()` is the soul's "search everything" entry point. The test seeds one episodic and one semantic memory with overlapping keywords, then confirms both appear in results. This guards against the recall engine silently ignoring a store during fan-out.

### Knowledge Graph

`test_knowledge_graph_add_and_query` tests the `KnowledgeGraph` sub-component directly via the manager. It verifies entity/relationship insertion and that relationship queries return connected entities — the primitive operations that support graph-augmented recall.

### Memory Removal

`test_memory_remove` seeds a memory, records its ID, removes it, and confirms it no longer appears in search results. This guards against soft-delete bugs where records are hidden but not actually removed.

### Clear Operation

```python
async def test_memory_manager_clear(manager):
    # core memory must survive clear()
```

`clear()` wipes episodic, semantic, and procedural stores but **intentionally preserves core memory**. Core holds the soul's identity and bonded-user profile — clearing that on session reset would destroy the soul's persistent identity. This test ensures the boundary is respected.

### Significance Short-Circuit (TestSignificanceShortCircuit)

A nested class tests the fast-path optimization where low-significance interactions skip steps 5 and 6 (entity extraction + graph update):

- Trivial interactions (low score) skip extraction
- Significant interactions run the full pipeline
- The return shape is identical either way (no API surface change)
- Disabling the flag with `enable_significance_gate=False` forces full pipeline always
- Fact promotion (even from a trivial interaction) still triggers extraction

This optimization prevents wasted LLM calls on "ok", "thanks", and other noise.

### Known Gaps

No explicit TODO/FIXME markers. The significance short-circuit tests use mocks rather than a real LLM, so they test the routing logic but not extraction quality.
