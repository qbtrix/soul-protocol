---
{
  "title": "Five Experimental Memory Conditions for Soul Protocol Ablation Study",
  "summary": "Implements the five independent-variable conditions for the Soul Protocol validation study, ranging from a completely stateless baseline to the full psychology-informed stack. Each condition is a class that wraps a Soul (or no Soul) and exposes a uniform `observe / recall / get_state / reset` interface, allowing the experiment runner to swap conditions without changing any other code.",
  "concepts": [
    "ablation study",
    "memory conditions",
    "BaseCondition",
    "NoMemoryCondition",
    "RAGOnlyCondition",
    "RAGSignificanceCondition",
    "FullNoEmotionCondition",
    "FullSoulCondition",
    "ObserveResult",
    "LIDA significance gating",
    "somatic markers",
    "bond tracking",
    "factory pattern",
    "polymorphic interface"
  ],
  "categories": [
    "research",
    "experimental-design",
    "soul-protocol",
    "ablation"
  ],
  "source_docs": [
    "1c89c022b9cf7576"
  ],
  "backlinks": null,
  "word_count": 538,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`conditions.py` is the heart of the ablation experiment. It defines five classes that each represent a different level of memory sophistication, answering the question: *which parts of Soul Protocol actually drive the quality improvements?*

## Design: Polymorphic Condition Interface

`BaseCondition` defines the interface all conditions must implement:

```python
class BaseCondition:
    async def setup(self, agent_profile: Any) -> None: ...
    async def observe(self, interaction: Interaction) -> ObserveResult: ...
    async def recall(self, query: str, limit: int = 10) -> list[MemoryEntry]: ...
    async def get_state(self) -> dict[str, Any]: ...
    async def reset(self) -> None: ...
```

The `create_condition(condition)` factory returns the right class instance. This means the experiment runner is fully decoupled from condition implementation details — it only speaks the `BaseCondition` interface.

## The Five Conditions

### Condition 1: NoMemoryCondition (Stateless Baseline)
No soul is created. `observe()` increments a counter and returns zeroed `ObserveResult` fields. `recall()` always returns an empty list. This is the null hypothesis — an LLM with no memory at all. Every other condition should outperform this.

### Condition 2: RAGOnlyCondition
A soul is created, but the extraction pipeline is bypassed. Every interaction is stored verbatim as a semantic memory with fixed importance 5:

```python
content = f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"
await self._soul.remember(content, importance=5)
```

This simulates naive vector-store RAG: everything goes in, nothing is filtered. This condition answers whether significance gating matters — if RAGOnly performs near Full Soul, gating is not worth the complexity.

### Condition 3: RAGSignificanceCondition
Uses the full `soul.observe()` pipeline (which applies LIDA significance gating) but strips the somatic (emotional) markers from the returned `ObserveResult`. This isolates the contribution of significance gating alone, separate from emotional modeling.

### Condition 4: FullNoEmotionCondition
Full pipeline minus somatic markers and bond tracking. Significance gating is active, memory categories are applied, but the soul does not model emotional states or track relationship depth. This isolates the contribution of emotional continuity.

### Condition 5: FullSoulCondition
The complete Soul Protocol stack. All features active: significance gating, somatic markers, bond tracking, skill registry, memory categories, and emotional state modeling. This is the treatment group.

## ObserveResult: Standardized Measurement

```python
@dataclass
class ObserveResult:
    facts_extracted: list[str]
    entities_extracted: list[str]
    significance_score: float
    somatic_valence: float | None
    stored_episodic: bool
    bond_strength: float
    skills_count: int
    memory_count: int
```

Every condition returns this same structure after each `observe()` call. Fields that the condition doesn't compute are set to zero/None rather than being omitted. This uniformity means the metrics collector can process all conditions identically — no condition-specific branching in the measurement code.

## Reset Semantics

`reset()` clears per-scenario state but not cross-session memory. This distinction is deliberate: the experiment simulates multiple sessions with a user, and persistent memory across sessions is what's being tested. Resetting everything between sessions would defeat the purpose.

Only `NoMemoryCondition.reset()` actually zeroes state (its interaction counter). The soul-based conditions leave memory intact across resets.

## Known Gaps

- `RAGSignificanceCondition.observe()` calls `await self._soul.observe(interaction)` to get significance gating, but then returns zeroed `facts_extracted` and `entities_extracted`. This means the experiment cannot measure whether gating changes extraction quality, only whether it changes recall outcomes.
- The `create_condition()` factory function is referenced in the AST summary but its implementation was not extracted — the mapping from `MemoryCondition` enum values to concrete classes is not visible in the snapshot.