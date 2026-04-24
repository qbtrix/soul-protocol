---
{
  "title": "LearningEvent — Formalized Lesson Model for Procedural Memory and Skill XP",
  "summary": "`LearningEvent` captures insights extracted from evaluating success and failure — distinct from episodic memory (what happened) and semantic memory (what is known). Stored in procedural memory and linked to skills, it drives reinforcement-style confidence updates through `apply()`, `reinforce()`, and `weaken()` methods.",
  "concepts": [
    "LearningEvent",
    "procedural memory",
    "confidence",
    "reinforce",
    "weaken",
    "apply",
    "domain",
    "skill_id",
    "evaluation",
    "lesson extraction",
    "Hebbian learning",
    "XP grant"
  ],
  "categories": [
    "memory",
    "learning",
    "spec layer",
    "procedural memory"
  ],
  "source_docs": [
    "538efaf75d2ebf42"
  ],
  "backlinks": null,
  "word_count": 547,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Souls learn not just by accumulating facts or recording events, but by extracting generalizable lessons from experience. A soul that fails at a task should update its internal model of how to approach similar tasks in the future. `LearningEvent` formalizes that process.

This is the third memory tier: episodic stores what happened, semantic stores what is known, and procedural stores how to do things. `LearningEvent` sits in procedural memory because lessons are action-oriented — they change future behavior rather than just recording past state.

## Model Definition

```python
class LearningEvent(BaseModel):
    id: str
    trigger_interaction_id: str | None  # What caused this learning
    lesson: str                         # The actual insight
    domain: str = "general"             # Maps to evaluation rubric domains
    confidence: float = 0.5             # 0.0 to 1.0
    skill_id: str | None                # Links to skill for XP
    evaluation_score: float | None      # From Evaluator
    applied_count: int = 0
```

### `lesson`
The human-readable insight text — e.g., `"When summarizing technical docs, use bullet points rather than paragraphs."` This is what the soul recalls when approaching a similar domain task.

### `confidence`
Starts at `0.5` (uncertain). Updated by reinforcement:
- `reinforce(amount=0.1)` — called when applying the lesson produces a good outcome. Caps at `1.0`.
- `weaken(amount=0.1)` — called when the lesson proves wrong. Floors at `0.0`.
- `apply()` — increments `applied_count` to track how often the lesson is used.

This is a simple Hebbian-style pattern: lessons that get used and proven correct accumulate confidence; lessons that lead to failures lose confidence and eventually stop being recalled.

### `domain`
Maps to the evaluation rubric's domain taxonomy (e.g., `"summarization"`, `"code_generation"`, `"empathy"`). When the retrieval layer searches for relevant lessons before a task, it can filter by domain to avoid surfacing unrelated lessons.

### `skill_id`
Optional link to a specific skill. When a lesson is reinforced, the linked skill may receive an XP grant. This connects the learning system to the skill progression system without tight coupling — skills exist independently; `LearningEvent` just references their ID.

### `trigger_interaction_id`
Traces back to the interaction that generated this lesson. Used by the evaluation pipeline to correlate lessons with the specific conversational turn or task that revealed the insight.

## Lifecycle

```
Evaluator runs after interaction
  └─ Extracts lesson from success/failure
       └─ LearningEvent created (confidence=0.5)
            └─ Stored in procedural memory
                 └─ Later recalled for similar domain task
                      └─ lesson.apply()      # count++
                           └─ outcome good?
                                yes: lesson.reinforce()
                                no:  lesson.weaken()
```

## Why Not Just Use Semantic Memory?

Semantic memory stores facts about the world (`"The capital of France is Paris"`). A `LearningEvent` stores a behavioral directive (`"When asked about capitals, confirm the current year before answering"`). The distinction matters for retrieval: when preparing for a task, the runtime searches procedural memory for applicable lessons, not the full semantic store.

## Known Gaps

- The module header notes it was added to unblock an import: the file was referenced by `spec/__init__.py` but the actual implementation lived in a different feature branch (`feat/graph-learning-events`, PR #115). This is a known coordination gap — the spec model was added as a stub to unblock the dependent PR.
- No decay mechanism over time. Confidence can only change when `reinforce()` or `weaken()` is explicitly called; there is no passive forgetting for lessons that haven't been applied in a long time.