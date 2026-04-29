---
{
  "title": "DSPy Integration Test Suite — Cognitive Processor, Adapter, and Optimizer",
  "summary": "Test suite for the DSPy-powered cognitive layer in soul-protocol, covering module instantiation, the `DSPyCognitiveProcessor` adapter bridge, training data generation, graceful fallback when DSPy is absent, and the `SoulOptimizer`. All LLM calls are mocked — no real API calls are made.",
  "concepts": [
    "DSPy",
    "SignificanceGate",
    "QueryExpander",
    "FactExtractor",
    "DSPyCognitiveProcessor",
    "SoulOptimizer",
    "training data generator",
    "graceful fallback",
    "sys.modules mock",
    "use_dspy flag",
    "cognitive processor",
    "mock dspy"
  ],
  "categories": [
    "testing",
    "dspy",
    "cognitive-processing",
    "test"
  ],
  "source_docs": [
    "35eb91f45ccc2285"
  ],
  "backlinks": null,
  "word_count": 444,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

DSPy is an optional dependency that upgrades soul-protocol's cognitive processing from rule-based heuristics to learned LLM-backed modules. This test suite validates the integration layer: DSPy modules (`SignificanceGate`, `QueryExpander`, `FactExtractor`), the adapter that bridges them to the Soul runtime, training data generation, and the optimizer. Since DSPy is optional, the suite also validates graceful degradation when the package is absent.

## Why This Exists

DSPy integration introduces a hard dependency boundary: the rest of soul-protocol must work identically whether DSPy is installed or not. If the import guard fails, production souls would crash on startup. The tests enforce this boundary rigorously.

## Mock Infrastructure

```python
def _mock_dspy_module():
    mock_dspy = MagicMock()
    mock_dspy.LM.return_value = mock_lm
    mock_dspy.configure = MagicMock()
    # ChainOfThought returns prediction-like objects
    ...

@contextmanager
def _with_mock_dspy():
    # Injects mock dspy into sys.modules, ensures cleanup
    ...
```

`_with_mock_dspy()` is a context manager that injects a mock dspy module into `sys.modules` for the duration of a test block and cleans up afterward. This prevents test pollution across the session — a real concern because module imports are global state.

## DSPy Module Tests

`TestDSPyModulesImport` instantiates and calls forward on each module (`SignificanceGate`, `QueryExpander`, `FactExtractor`) with mock DSPy active. This catches broken `__init__` signatures or missing ChainOfThought wiring.

## Adapter Bridge Tests

`TestDSPyAdapter` tests `DSPyCognitiveProcessor` — the async adapter that wraps DSPy modules for the soul runtime:

- `test_assess_significance_returns_score` — verifies a float 0-1 is returned
- `test_expand_query_returns_list` — verifies query expansion returns a list of strings
- `test_extract_facts_returns_memory_entries` — verifies fact extraction returns `MemoryEntry` objects
- `test_assess_significance_fallback_on_error` — if DSPy throws, the adapter returns a default score rather than propagating. This prevents a DSPy outage from crashing memory ingestion.

## Training Data Generator

`TestTrainingDataGenerator` verifies that `generate_significance_dataset()` and `generate_recall_dataset()` produce valid examples with the correct structure. Critically, `test_significance_dataset_has_both_labels` ensures negative examples exist — a bug was found and fixed where `assert negatives >= 0` was used instead of `assert negatives > 0`.

## Default-Off Path

`TestDSPyDefaultOff` verifies that `Soul.birth(use_dspy=False)` and the default (`use_dspy` unset) produce souls that behave identically to the pre-DSPy implementation. No DSPy imports occur on these paths.

## Missing Dependency Handling

`TestDSPyNotInstalled` patches `sys.modules` to simulate DSPy being absent:
- `test_dspy_modules_import_error` verifies the import raises cleanly
- `test_soul_birth_with_dspy_true_no_package` verifies that requesting DSPy when it's not installed raises a clear error rather than a confusing `AttributeError`

## Helper Utilities

`TestHelpers` validates `safe_float()` and `clamp()` — small utilities used throughout the adapter. Testing these separately prevents subtle float-conversion bugs from hiding in higher-level test failures.

## Known Gaps

The optimizer tests (`TestDSPyOptimizer`) only test instantiation and the metric function — they do not test an actual optimization loop, which would require a real DSPy LM.