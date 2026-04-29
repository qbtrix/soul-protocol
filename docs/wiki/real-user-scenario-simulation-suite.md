---
{
  "title": "Real-User Scenario Simulation Suite",
  "summary": "A comprehensive integration simulation that runs six realistic user scenarios against soul-protocol to validate lifecycle correctness, memory accuracy, multi-format support, personality divergence, and resilience. Each scenario produces a structured pass/fail report written to `.results/`.",
  "concepts": [
    "scenario simulation",
    "Soul.birth",
    "Soul.awaken",
    "export import roundtrip",
    "OCEAN personality",
    "memory recall",
    "resilience testing",
    "multi-format support",
    "CheckResult",
    "ScenarioResult",
    "Interaction",
    "developer onboarding"
  ],
  "categories": [
    "scripts",
    "integration-testing",
    "simulation"
  ],
  "source_docs": [
    "e2478a31bc19f759"
  ],
  "backlinks": null,
  "word_count": 500,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`simulate_real_users.py` validates soul-protocol against realistic usage patterns that unit tests cannot easily cover. It sits between unit tests (which verify individual functions) and production deployments (which have real users). The six scenarios collectively exercise every major code path from birth to archival.

## Why It Exists

Soul-protocol's core promise — that memories persist, identities stay consistent, and exports round-trip cleanly — can only be verified by running real workflows. Edge cases like partial exports, corrupted archives, or personality drift under different OCEAN profiles only appear at integration depth.

## Scenarios

### 1. Developer Onboarding (`scenario_developer_onboarding`)
Births a fresh soul, runs 20 developer Q&A interactions, then checks that domain-relevant memories were stored and that the self-model's domain field evolved away from the seed value. This validates the full observe → compress → recall pipeline for a common usage pattern.

### 2. Long-Running Assistant (`scenario_long_running_assistant`)
Runs 100+ interactions and then spot-checks that specific facts can be recalled by keyword. This guards against memory recall accuracy degrading as the store grows — a regression that only appears at scale.

### 3. Export/Import Roundtrip (`scenario_export_import_roundtrip`)
Births a soul, accumulates interactions, exports to a `.soul` zip archive, awakens a new soul from that archive, and then verifies that every memory present before export is present after import. This is the critical data-durability test.

### 4. Multi-Format Support (`scenario_multi_format_support`)
Births souls from four different config representations (YAML, JSON, `.soul` file, `.soul/` directory) and checks that each produces a working soul. Prevents format-specific parsing regressions.

### 5. Personality Expression (`scenario_personality_expression`)
Creates two souls with opposite OCEAN profiles (high Openness vs. low Openness) and feeds them identical interactions. Checks that the resulting emotional states and memory salience differ — validating that personality actually influences processing, not just metadata.

### 6. Recovery/Resilience (`scenario_recovery_resilience`)
Tests corrupt-file handling, missing config fields, and backward-compatibility with older soul formats. If this scenario passes, soul-protocol degrades gracefully rather than crashing on malformed input.

## Data Flow

```python
Soul.birth() / Soul.awaken()
        │
        ▼
soul.observe(Interaction(...))  ← repeated N times
        │
        ▼
soul.recall(query)  ← spot-checks
        │
        ▼
CheckResult(name, passed, detail)  → ScenarioResult
        │
        ▼
_write_scenario_results()  →  .results/simulation_<name>.json
```

## Key Types

| Type | Role |
|------|------|
| `CheckResult` | Single assertion: name, passed bool, detail string |
| `ScenarioResult` | Aggregates checks for one scenario, tracks elapsed ms |
| `Soul` | The runtime soul under test |
| `Interaction` / `Mood` | Core interaction primitives |

## Running

```bash
uv run python scripts/simulate_real_users.py
uv run python scripts/simulate_real_users.py --scenario developer_onboarding
uv run python scripts/simulate_real_users.py --list
```

## Known Gaps

- The domain check in `scenario_developer_onboarding` was relaxed (2026-03-02) to accept emergent domain names beyond the seed `technical_helper`. This means the check can pass even if domain evolution is noisy.
- Scenarios write to `.results/` but do not assert on prior runs, so a regression could exist in an older result file without triggering a failure on re-run.
- No timeout guard on individual scenarios; a hung async call would block the entire suite indefinitely.
