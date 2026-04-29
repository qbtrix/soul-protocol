---
{
  "title": "Memory Categories and Salience Scoring Example",
  "summary": "Demonstrates Soul Protocol's v0.2.3 memory extraction taxonomy by walking through the observe pipeline with five realistic interactions, then inspecting how the system assigns categories, salience scores, and memory types to extracted facts. The example also shows the deduplication pipeline and progressive content loading (L0/L1/L2) through targeted recall queries.",
  "concepts": [
    "memory categories",
    "salience scoring",
    "observe pipeline",
    "entity extraction",
    "significance gating",
    "deduplication",
    "Soul.birth",
    "Soul.observe",
    "Soul.recall",
    "MemoryType",
    "episodic memory",
    "semantic memory",
    "procedural memory",
    "progressive content loading"
  ],
  "categories": [
    "examples",
    "memory",
    "soul-protocol",
    "data-flow"
  ],
  "source_docs": [
    "24e6ab4942e3f7af"
  ],
  "backlinks": null,
  "word_count": 563,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`memory_categories.py` teaches developers how Soul Protocol classifies and scores memories — not just that memories are stored, but *how* the pipeline decides what matters and how to label it. Without this example, integrators would treat `soul.observe()` as a black box and struggle to predict which facts survive the significance gate.

## The Observe Pipeline

Every call to `soul.observe(Interaction(...))` triggers a multi-step extraction pipeline:

1. **Entity extraction** — named entities (people, organizations, tools) are identified
2. **Fact decomposition** — the interaction is split into atomic factual claims
3. **Significance scoring** — each fact is scored against the soul's values and prior memories
4. **Category assignment** — facts are tagged with one of seven memory categories
5. **Salience computation** — a composite float (0-1) is assigned based on recency, importance, and emotional weight
6. **Deduplication** — near-duplicate facts are merged or suppressed
7. **Storage** — significant facts are written to the memory store

## Soul Construction

```python
soul = await Soul.birth(
    name="Echo",
    archetype="The Knowledge Curator",
    values=["accuracy", "organization", "learning"],
)
```

The `values` list directly influences significance scoring. A soul that values `"accuracy"` will score factual corrections higher than small talk. The archetype shapes the soul's persona string but also primes its extraction heuristics.

## Example Interactions and What They Demonstrate

The five interactions cover a range of memory categories intentionally:

| Interaction | Expected category |
|---|---|
| "My name is Alex, data engineer at Acme Corp" | Entity / identity |
| "I prefer Python over Java" | Preference / belief |
| "We had an outage last Tuesday" | Episodic event |
| "The fix was retry with exponential backoff" | Procedural knowledge |
| "I like working with Apache Spark" | Interest / affinity |

This spread ensures the example exercises all major branches of the extraction taxonomy rather than producing homogeneous semantic memories.

## Inspecting Memory Metadata

After observing, the example runs three recall queries to show metadata fields:

```python
for m in memories:
    cat = f" [{m.category.value}]" if hasattr(m, "category") and m.category else ""
    sal = f" salience={m.salience:.2f}" if hasattr(m, "salience") and m.salience else ""
    print(f"  [{m.type.value}]{cat}{sal} {m.content[:80]}")
```

The defensive `hasattr` guards handle older memory entries that predate v0.2.3's category/salience fields — this is a forward-compatibility pattern for souls migrated from earlier versions.

## Recall Specificity

Three queries demonstrate how recall targeting works:
- `"Alex data engineer"` — broad identity query
- `"Python"` — narrow technology preference
- `"outage crash"` — event recall using related terms

The multi-term query for the outage shows that recall uses semantic similarity, not exact match — `"outage crash"` retrieves the Tuesday outage memory even though neither word appears verbatim.

## State After Processing

The final state check (`soul.state.mood`, `soul.state.energy`) demonstrates that observing interactions is not side-effect-free. Processing emotionally charged events (like the outage) consumes energy and may shift mood. Integrators who ignore state risk building agents that become unresponsive after heavy interaction loads.

## Known Gaps

- The L0/L1/L2 progressive content loading mentioned in the file header is referenced in the docstring but the actual API for requesting different content tiers is not demonstrated in the extracted body — the example only shows `m.content`, `m.abstract` (L1), but does not show L2 retrieval.
- The seven memory categories are referenced but not enumerated in the code; developers need to check the `MemoryCategory` enum in the core SDK to see the full list.