---
{
  "title": "Simulation Engine: Full Factorial Experiment Orchestrator for Soul Protocol Research",
  "summary": "The `SimulationEngine` orchestrates the core ablation study by running every combination of (agent, condition, use_case) as an async task, collecting `AgentRunMetrics` for each triple, and aggregating them into a `SimulationResults` object. Failed individual runs are logged and skipped rather than crashing the whole experiment, ensuring partial results are always captured.",
  "concepts": [
    "SimulationEngine",
    "_RunSpec",
    "SimulationResults",
    "ExperimentConfig",
    "AgentRunMetrics",
    "factorial experiment",
    "async batching",
    "fault isolation",
    "ProgressCallback",
    "ConditionType",
    "to_dataframe_rows"
  ],
  "categories": [
    "research",
    "simulation",
    "orchestration",
    "soul-protocol"
  ],
  "source_docs": [
    "d2a9761d8a5eb158"
  ],
  "backlinks": null,
  "word_count": 383,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

A factorial experiment over 1000 agents × 4 conditions × 4 use cases produces 16,000 individual runs. Orchestrating this correctly requires async batching (to avoid blocking), fault isolation (one bad agent must not abort the other 15,999), and a result container that supports both in-memory analysis and on-disk persistence.

`SimulationEngine` is the component that handles all three.

## Architecture

```python
class SimulationEngine:
    def __init__(
        self,
        config: ExperimentConfig,
        *,
        batch_size: int,
        progress_callback: ProgressCallback | None,
    ) -> None:
```

`batch_size` controls how many `_RunSpec` triples are dispatched concurrently via `asyncio.gather`. The default (50) is calibrated to avoid overwhelming the Soul Protocol runtime's internal state while still achieving useful parallelism.

## Run Isolation

```python
async def _run_single(self, agent_profile, user_profile, condition_type, use_case) -> AgentRunMetrics:
    try:
        condition = create_condition(condition_type)
        await condition.setup(agent_profile)
        for turn in scenario.turns:
            result: ObserveResult = await condition.observe(turn.user_input, turn.agent_output)
        return compute_metrics(condition, scenario)
    except Exception as e:
        logger.error("Run failed: %s / %s / %s: %s", agent_profile.name, condition_type, use_case, e)
        self.results.errors.append({"agent": agent_profile.name, ...})
        return AgentRunMetrics(agent_id=agent_profile.name, ...)  # zeroed metrics
```

The try/except around each `_run_single` is the key fault-isolation mechanism. Without it, a single malformed agent profile or network timeout would abort all pending `asyncio.gather` tasks. With it, failed runs contribute zeroed metrics to the aggregate (which slightly biases averages downward) but never stop the experiment.

## _RunSpec

```python
@dataclass
class _RunSpec:
    agent_profile: AgentProfile
    user_profile: UserProfile
    condition_type: ConditionType
    use_case: UseCase
```

Representing each experiment cell as a lightweight struct (rather than passing four parameters) allows the run queue to be built upfront, shuffled if needed, and batched cleanly.

## SimulationResults

```python
@dataclass
class SimulationResults:
    all_metrics: list[AgentRunMetrics]
    config: ExperimentConfig
    duration_seconds: float
    errors: list[dict]

    def to_dataframe_rows(self) -> list[dict]:
        return [m.to_row() for m in self.all_metrics]

    def save(self, path: str | Path) -> Path:
        # Serialize as JSON
```

`to_dataframe_rows()` produces a flat list of dicts, making it trivial to load results into pandas or any tabular analysis tool. The `errors` list provides a post-run audit trail without cluttering the metrics.

## Known Gaps

- Progress reporting via `ProgressCallback` is optional. When omitted, long runs (>30 min) give no feedback, making it hard to distinguish a slow run from a hung process.
- Zeroed metrics from failed runs silently bias aggregates. A cleaner design would exclude errors from averages and report a separate "valid run count" alongside each aggregate.
