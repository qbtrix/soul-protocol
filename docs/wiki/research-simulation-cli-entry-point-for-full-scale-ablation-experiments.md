---
{
  "title": "Research Simulation CLI: Entry Point for Full-Scale Ablation Experiments",
  "summary": "The `run.py` module is the primary CLI entry point for the Soul Protocol research simulation framework, translating command-line arguments into an `ExperimentConfig` and orchestrating the full simulation, analysis, and report pipeline. It supports configuring agent count, random seed, memory conditions, use cases, output directory, batch size, and a quick mode for rapid iteration.",
  "concepts": [
    "ExperimentConfig",
    "MemoryCondition",
    "UseCase",
    "SimulationEngine",
    "CLI entry point",
    "ablation study",
    "batch size",
    "quick mode",
    "resolve_conditions",
    "resolve_use_cases",
    "research pipeline"
  ],
  "categories": [
    "research",
    "cli",
    "simulation",
    "soul-protocol"
  ],
  "source_docs": [
    "1e8c2f3362f54b0e"
  ],
  "backlinks": null,
  "word_count": 418,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Large-scale ablation studies need a controlled, reproducible entry point. `run.py` serves as the single command that launches the full research pipeline — from argument parsing through simulation execution to written reports. Its existence as a standalone CLI (rather than embedded test code) reflects a design choice: research experiments are long-running, expensive, and need to be invoked selectively and repeatedly with different parameters.

## CLI Arguments

| Argument | Default | Purpose |
|---|---|---|
| `--agents N` | 1000 | Number of simulated agents |
| `--seed N` | 42 | Random seed for reproducibility |
| `--conditions LIST` | all | Comma-separated `MemoryCondition` values |
| `--use-cases LIST` | all | Comma-separated `UseCase` values |
| `--output DIR` | `research/results` | Results output directory |
| `--batch-size N` | 50 | Parallel async batch size |
| `--quick` | false | 10 agents, 2 conditions, 1 use case |

The `--quick` flag is essential for development: running 1000 agents against all conditions costs real time and money. Quick mode lets a developer verify the pipeline works before committing to a full run.

## Argument Resolution

`resolve_conditions` and `resolve_use_cases` convert comma-separated strings to typed enum lists. They validate each token against the enum and raise immediately on unknown values, preventing silent configuration errors. The pattern is defensive: a typo in `--conditions full_sowl` fails loudly rather than silently skipping the intended condition.

```python
def resolve_conditions(raw: str | None) -> list[MemoryCondition]:
    if raw is None:
        return list(MemoryCondition)  # all conditions if unspecified
    # validate each token against enum values
```

## Execution Flow

```
parse_args()
  └── build_config()    → ExperimentConfig
        └── print_plan() → stdout experiment summary before execution
              └── SimulationEngine.run() → SimulationResults
                    └── print_headline()  → key metrics to stdout
                          └── Analyzer.generate_report() → saved files
```

`print_plan()` prints the experiment configuration before any API calls are made. This is a guard against accidentally launching a 1000-agent, all-condition run when a quick test was intended.

## Output

The async `run()` function delegates simulation to `SimulationEngine` and analysis to an `Analyzer`. Results are written to the output directory as JSON (machine-readable) and Markdown (human-readable). Timestamps in filenames prevent clobbering previous runs.

## Known Gaps

- `print_headline()` extracts key metrics (soul vs baseline win rates) from `SimulationResults` but does not include statistical significance. A researcher comparing two runs must manually apply significance tests to the saved JSON.
- `--batch-size` controls async parallelism but has no upper bound validation. Setting it too high can overwhelm both the Soul Protocol runtime and Anthropic's rate limits simultaneously.
