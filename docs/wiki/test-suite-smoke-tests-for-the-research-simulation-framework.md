---
{
  "title": "Test Suite: Smoke Tests for the Research Simulation Framework",
  "summary": "This test suite validates that all research framework components — agent generation, user generation, scenario generation, experiment configuration, metrics, statistical utilities, and memory conditions — work correctly at minimal scale without requiring any LLM API calls. It is fast enough for CI and guards against regressions in the framework before running expensive full ablations.",
  "concepts": [
    "smoke tests",
    "test_agent_generation",
    "test_user_generation",
    "ExperimentConfig",
    "AgentRunMetrics",
    "to_row",
    "cohens_d",
    "confidence_interval_95",
    "mann_whitney_u",
    "NoMemoryCondition",
    "OCEAN traits",
    "CI testing"
  ],
  "categories": [
    "research",
    "testing",
    "simulation",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "c0aacc7e30b1ac77"
  ],
  "backlinks": null,
  "word_count": 377,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

This is the test suite for the Soul Protocol research simulation framework. Before spending API budget on a 1000-agent ablation, these smoke tests verify that the framework's data structures, generators, and statistics are internally consistent. A bug in `generate_agents()` or `AgentRunMetrics.to_row()` would corrupt all downstream results silently; these tests catch such bugs cheaply.

## Test Coverage

### Agent Generation (`test_agent_generation`)
- Generates 10 agents and verifies OCEAN traits are within `[0.05, 0.95]` (truncated normal bounds)
- Asserts names are unique to prevent index collisions
- Validates derived behavioral tendencies (`emotional_reactivity == ocean["neuroticism"]`) are correctly computed from OCEAN values
- Checks communication style values are from the valid set

### User Generation (`test_user_generation`)
- Generates 10 users per use case, verifying required fields exist

### Scenario Generation (`test_scenario_generation`)
- Verifies turns have all required ground-truth fields (`contains_fact`, `fact_content`, etc.)

### Config Validation
- `test_config_defaults`: asserts that `ExperimentConfig()` initializes with sensible defaults (not zeros or None)
- `test_config_total_runs`: verifies `total_runs == num_agents * len(conditions) * len(use_cases)`, catching integer math errors in the config

### Metrics
- `test_metrics_to_row`: creates an `AgentRunMetrics` with all sub-metrics populated and verifies `to_row()` returns a flat dict with all expected keys — prevents column-drop bugs when serializing to JSON

### Statistical Utilities
- `test_statistical_utils`: tests `cohens_d`, `confidence_interval_95`, and `mann_whitney_u` with known analytical values, ensuring statistical functions produce correct results before they are applied to real data

### Memory Condition (`test_no_memory_condition`)
- Creates a `NoMemoryCondition`, calls `setup()` and `observe()`, and asserts that `recall()` returns an empty list — verifies the baseline condition does not accidentally store anything

## Design Principles

All tests run without any LLM calls. `HaikuCognitiveEngine` is never instantiated in this suite. This keeps CI fast (sub-second) and cost-free, which is critical for a research codebase where the real experiments are already expensive.

```python
@pytest.mark.asyncio
async def test_no_memory_condition():
    condition = NoMemoryCondition()
    await condition.setup(agent_profile)
    result = await condition.observe("hello", "hi")
    assert result.memories_recalled == []
```

## Known Gaps

- There are no tests for `generate_scenarios()` with edge cases (e.g., a `UserProfile` with unusual values). The scenario generator uses randomized content but only standard profiles are tested.
- `test_statistical_utils` tests known analytical values but does not test edge cases like empty lists, single-element lists, or distributions with zero variance, which can cause division-by-zero in `cohens_d`.
