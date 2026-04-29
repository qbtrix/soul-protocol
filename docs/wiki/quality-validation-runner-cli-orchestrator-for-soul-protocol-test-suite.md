---
{
  "title": "Quality Validation Runner: CLI Orchestrator for Soul Protocol Test Suite",
  "summary": "The quality runner provides a command-line interface to execute one or more of the four fixed validation tests (response quality, personality consistency, hard recall, emotional continuity) and outputs both a live scorecard and saved JSON/Markdown reports. It uses concurrent `HaikuCognitiveEngine` instances for agent and judge roles to keep cost tracking separate.",
  "concepts": [
    "run_quality",
    "quality validation",
    "test registry",
    "HaikuCognitiveEngine",
    "CLI runner",
    "scorecard",
    "soul_score",
    "baseline_score",
    "response quality",
    "personality consistency",
    "hard recall",
    "emotional continuity",
    "concurrent execution"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "cli",
    "soul-protocol"
  ],
  "source_docs": [
    "6d6143b53930698b"
  ],
  "backlinks": null,
  "word_count": 386,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol needs empirical evidence that a soul improves agent behavior before those claims can be made publicly. `run_quality.py` is the harness that runs the evidence-gathering tests in a repeatable, auditable way. It is intentionally a standalone CLI — not embedded in pytest — because the tests involve real LLM calls and can be expensive; running them selectively (`--tests recall`) avoids unnecessary API spend.

## CLI Interface

```
python -m research.quality.run_quality
python -m research.quality.run_quality --tests recall,emotional
python -m research.quality.run_quality --output results/ --max-concurrent 5
```

The `--tests` flag accepts a comma-separated list of short names from `ALL_TEST_NAMES`. Validation in `_resolve_tests` rejects unknown names immediately, preventing silent no-ops when a test name is misspelled.

## Test Registry

```python
TEST_REGISTRY: dict[str, tuple[str, Any]] = {
    "response":    ("Response Quality",       test_response_quality),
    "personality": ("Personality Consistency", test_personality_consistency),
    "recall":      ("Hard Recall",            test_hard_recall),
    "emotional":   ("Emotional Continuity",   test_emotional_continuity),
}
```

The registry pattern decouples the CLI from the test implementations. Adding a fifth test requires only a new entry here — no branching in `run()`.

## Execution Flow

```
parse args
  └── resolve_tests() → ordered list of test keys
        └── for each test: call async function → dict with soul_score / baseline_score
              └── _winner(soul, baseline) → "SOUL" | "BASELINE" | "TIE"
                    └── print scorecard row
  └── save JSON + Markdown to output directory
```

Concurrency is bounded by `--max-concurrent` (default 5). This prevents overwhelming the Soul Protocol runtime and Anthropic's rate limiter simultaneously.

## Scorecard Output

The live console scorecard uses `_fmt(val, width)` to align numeric scores in fixed-width columns. This is aesthetic but matters in practice: misaligned numbers in long terminal output are hard to scan quickly. The saved Markdown report duplicates the same data for async review (e.g., in CI artifacts).

## Output Files

Two files per run:
- `results_<timestamp>.json` — machine-readable, suitable for programmatic comparison across runs
- `results_<timestamp>.md` — human-readable, suitable for PR comments and research notes

Timestamping prevents clobbering previous runs and allows regression detection over time.

## Known Gaps

- No statistical aggregation across multiple runs. Each invocation produces a single score per test, so detecting improvements requires manual comparison rather than automated significance testing. The scenario generator produces 10 variations, but the runner does not automatically average across them.
- `--max-concurrent` applies globally, not per test. Tests with many sub-scenarios could starve others in a concurrent run.
