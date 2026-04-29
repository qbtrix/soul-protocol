---
{
  "title": "Test Suite: Cross-Session Contradiction Detection in the Observe Pipeline",
  "summary": "End-to-end regression tests for Soul Protocol's contradiction detection, targeting a specific bug where heuristic contradiction detection fired in isolation but silently failed during `observe()` when a user updated a fact across sessions (e.g., location or employer change). Tests verify that new facts correctly supersede old ones.",
  "concepts": [
    "contradiction detection",
    "ContradictionDetector",
    "detect_heuristic",
    "observe pipeline",
    "semantic facts",
    "superseded facts",
    "cross-session memory",
    "fact retirement",
    "location update",
    "employer update",
    "false positive detection",
    "Soul.observe",
    "SemanticStore"
  ],
  "categories": [
    "testing",
    "contradiction detection",
    "memory",
    "observe pipeline",
    "test"
  ],
  "source_docs": [
    "f01cbe1acf9eb473"
  ],
  "backlinks": null,
  "word_count": 458,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_contradiction_pipeline.py` reproduces a class of bug that was subtle to diagnose: `ContradictionDetector.detect_heuristic()` worked correctly when called directly, but when triggered inside `observe()`, it failed to mark old semantic facts as superseded when a user provided updated information in a new session. The tests in this file serve as both regression tests and integration probes for the full observe pipeline.

## The Bug This Suite Addresses

```
# Scenario:
# Session 1: 'I live in NYC.'        -> stores semantic fact: location=NYC
# Session 2: 'I moved to Amsterdam.' -> should supersede the NYC fact
#
# Bug: In session 2, detect_heuristic() was called but the supersede write
# never propagated back to SemanticStore. The old fact remained active.
```

This is a silent correctness failure -- the soul would continue believing the user lives in NYC while also believing they live in Amsterdam, with no conflict flagged.

## Test Structure

Each test runs two `observe()` sessions on the same soul:

```python
async def test_location_contradiction_across_sessions(tmp_path):
    soul = await Soul.birth(name="TestSoul", soul_dir=str(tmp_path))

    # Session 1: establish location
    await soul.observe(Interaction(
        user_input="I live in NYC. I work at a startup called TechCorp.",
        agent_output="Great! NYC is exciting.",
    ))

    # Session 2: update location
    await soul.observe(Interaction(
        user_input="I moved to Amsterdam last week. Starting at Stripe.",
        agent_output="Amsterdam is wonderful!",
    ))

    semantics = soul._memory._semantic.facts(include_superseded=True)
    # Assert old NYC fact is superseded, Amsterdam fact is active
```

The `include_superseded=True` flag on `facts()` is key: it exposes all facts including retired ones, so the test can assert both that the new fact exists AND that the old fact was properly retired.

## Scenario Coverage

| Test | Old Fact | New Fact | Verification |
|------|----------|----------|-------------|
| `test_location_contradiction_across_sessions` | location=NYC | location=Amsterdam | NYC fact superseded |
| `test_employer_contradiction_across_sessions` | employer=TechCorp | employer=Stripe | TechCorp fact superseded |
| `test_contradiction_detection_returns_results` | verb-fact conflict | conflicting verb-fact | `detect_heuristic()` returns results |
| `test_non_contradiction_not_flagged` | unrelated facts | unrelated facts | no false positives |

The false-positive test is essential: an overly aggressive contradiction detector would flag unrelated facts as contradictions, degrading memory quality.

## Why Cross-Session Testing Matters

Contradiction detection that only works within a single session is nearly useless for a persistent AI companion. Users naturally update information about themselves over time -- where they live, where they work, what they prefer. The soul must handle these updates gracefully, retiring stale facts rather than accumulating contradictory beliefs.

The tests use `Soul.birth()` with a `soul_dir` parameter (file-backed) rather than in-memory, ensuring that session-to-session state actually persists and the contradiction detector reads from the durable store.

## Known Gaps

The test suite was created specifically for the `fix/contradiction-pipeline` branch. The `include_superseded=True` API on `SemanticStore.facts()` was added as part of this fix to make the superseded state observable in tests.