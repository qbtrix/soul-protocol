---
{
  "title": "Soul Health Score Evaluation Suite Runner",
  "summary": "Orchestrates the 7-dimension Soul Health Score evaluation, dynamically loading dimension runners, executing them sequentially, computing the weighted composite score, and returning a structured report. Serves as both a library function and a CLI tool.",
  "concepts": [
    "SHS suite runner",
    "DimensionResult",
    "SoulHealthReport",
    "compute_shs",
    "dimension weights",
    "dynamic loading",
    "importlib",
    "error isolation",
    "placeholder result",
    "quick mode",
    "CLI runner"
  ],
  "categories": [
    "evaluation",
    "soul-health-score",
    "orchestration"
  ],
  "source_docs": [
    "c77fcb6bd563c657"
  ],
  "backlinks": null,
  "word_count": 392,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The suite runner is the central coordinator for SHS evaluation. It abstracts away dimension discovery, error isolation, and score aggregation so callers only need to provide a seed, dimension selection, and quick-mode flag.

## Data Models

### DimensionResult
```python
@dataclass
class DimensionResult:
    dimension_id: int       # 1-7
    dimension_name: str
    score: float            # 0-100
    metrics: dict[str, Any] # named sub-metrics
    passed: list[str]       # metric names that met targets
    failed: list[str]       # metric names that missed targets
    notes: str              # human-readable summary
```

### SoulHealthReport
Wraps all seven `DimensionResult` objects with metadata (run_id, seed, timestamp, version) and the composite `soul_health_score`. The `to_dict()` method serializes to a JSON-friendly dict with datetime ISO conversion.

## Dimension Weights

```python
DIMENSION_WEIGHTS = {
    1: 0.20,  # Memory Recall
    2: 0.20,  # Emotional Intelligence
    3: 0.15,  # Personality Expression
    4: 0.15,  # Bond / Relationship
    5: 0.15,  # Self-Model
    6: 0.10,  # Identity Continuity
    7: 0.05,  # Portability
}
```

Weights sum to 1.0. Memory and Emotional Intelligence are weighted highest because they are the capabilities users experience most directly.

## Dynamic Dimension Loading

`_register_dimensions()` uses `importlib.import_module` to load each `d{N}_{name}` module at runtime:

```python
mod = importlib.import_module(module_path)
_DIMENSION_RUNNERS[dim_id] = mod.evaluate
```

Import errors are caught silently—a dimension with broken dependencies is skipped rather than crashing the entire suite. For missing dimensions, `_placeholder_result` inserts a zero-score result with notes `"Not yet implemented"`. This design allows the suite to run partially during active development.

## Error Isolation

Each dimension runs inside a `try/except Exception` block:
```python
try:
    result = await runner(seed=seed, quick=quick)
except Exception:
    logger.exception("D%d evaluation failed", dim_id)
    results.append(_placeholder_result(dim_id))
```

A bug in one dimension (e.g., a corpus file missing) produces a placeholder rather than aborting the run. The operator gets a partial report with clear indication of which dimensions failed.

## CLI Usage

```bash
python -m research.eval.suite --quick
python -m research.eval.suite --dimensions 1 2 4 --seed 99
python -m research.eval.suite --dashboard
python -m research.eval.suite --output report.json
```

`--quick` reduces turn counts across all dimensions for fast development iteration. `--dashboard` delegates to `report.print_dashboard` for the ANSI terminal view.

## Known Gaps

- Dimensions run **sequentially**, not in parallel. Running all 7 dimensions in full mode takes considerable wall-clock time. Parallelizing with `asyncio.gather` would require solving shared-state issues between dimensions.
- The `run_id` is a UUID4 generated fresh each run. There is no mechanism to resume a partially completed run.