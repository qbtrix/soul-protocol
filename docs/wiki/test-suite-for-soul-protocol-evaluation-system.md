---
{
  "title": "Test Suite for Soul Protocol Evaluation System",
  "summary": "Comprehensive tests for the heuristic evaluation engine, rubric models, and Evaluator class used to score AI companion responses across multiple quality dimensions. Covers model validation, scoring algorithms, domain auto-selection, history capping, and streak detection.",
  "concepts": [
    "evaluation",
    "rubric",
    "RubricCriterion",
    "RubricResult",
    "heuristic scorer",
    "completeness",
    "relevance",
    "empathy",
    "specificity",
    "Evaluator",
    "domain routing",
    "history cap",
    "streak detection",
    "DEFAULT_RUBRICS",
    "learning string"
  ],
  "categories": [
    "testing",
    "evaluation",
    "learning",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "ad4b46f6541078d5"
  ],
  "backlinks": null,
  "word_count": 536,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `test_evaluation.py` suite validates `soul_protocol.runtime.evaluation`, the subsystem that grades agent responses against structured rubrics. Quality evaluation is central to the soul's learning loop — without reliable scoring, the evolution and skill-leveling systems cannot receive trustworthy signals.

## Core Data Models

Three Pydantic models underpin the system:

- **`RubricCriterion`** — A single scoring axis (e.g. relevance, empathy). Weight defaults to `1.0` so unweighted rubrics behave intuitively.
- **`Rubric`** — A named collection of criteria that auto-generates its `id` from `name` when not supplied, preventing duplicate-ID bugs in serialisation while still allowing explicit IDs to be preserved.
- **`RubricResult`** — The output of a single evaluation pass, stamped with a UTC timestamp at construction.

```python
def _simple_rubric(name, domain) -> Rubric:
    """Build a minimal single-criterion rubric for testing."""
    ...

def _rubric_with_criteria(*names) -> Rubric:
    """Build a rubric with multiple named criteria, all weight=1.0."""
    ...
```

## Heuristic Scorer

The heuristic evaluator is stateless and deterministic, avoiding LLM calls for fast feedback. It scores four dimensions:

### Completeness
Proportional to response word count, capped at `1.0` for 40+ words. The 40-word boundary is tested exactly (`test_heuristic_evaluate_exactly_40_words`) to catch off-by-one regressions at the boundary.

### Relevance
Counts non-stop-word token overlap between user input and agent output. An empty user input yields `0.0` relevance (tested explicitly) because the overlap calculation would otherwise divide by zero or produce misleading scores.

### Empathy
Presence of empathy-marker words boosts the score. Technical responses without these markers return `0.0`, preventing false positives from accidentally technical vocabulary.

### Specificity
Tokens containing digits or code-like characters (brackets, dots) are counted as "technical". Plain conversational words score low, technical explanations score high.

### Weighted Average
`overall_score` is the weighted mean across all criteria, tested against a manually computed expected value to catch floating-point drift.

## Learning Feedback String

The evaluator emits a human-readable `learning_string` mentioning the rubric name, the strongest criterion, and the weakest. Tests verify all three fields appear, ensuring the string stays useful as a training signal when surfaced back to the model.

## Evaluator Class

`Evaluator` wraps the heuristic scorer with state:

- **Domain routing** — picks the rubric matching a given domain string. Falls back to `technical_helper` for unknown domains and defaults to it when no domain is specified.
- **Explicit rubric override** — passing a `Rubric` directly bypasses domain lookup entirely.
- **History capping** — history is capped at `max_history` (default 100). Without this guard, a long-running companion process would accumulate unbounded memory.
- **Domain stats** — `get_domain_stats()` returns `count`, `avg_score`, and `streak` for any domain. Stats for a domain with no history return zeros rather than raising `KeyError`.
- **Streak detection** — five or more consecutive high-scoring interactions are flagged as a streak, a signal used by higher-level evolution logic.

## Default Rubrics

Six seed domains ship with `DEFAULT_RUBRICS` (tested to confirm all 6 exist and each has at least one criterion). This prevents a silent regression where a domain is added to routing logic but its rubric is forgotten.

## Known Gaps

- The heuristic scorer is intentionally simplified; LLM-based scoring is not tested here and presumably lives in a separate integration test layer.
- Stop-word list completeness is not tested — borderline tokens could unexpectedly inflate or deflate relevance scores.