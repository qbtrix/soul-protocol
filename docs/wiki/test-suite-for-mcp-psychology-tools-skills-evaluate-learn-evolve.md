---
{
  "title": "Test Suite for MCP Psychology Tools (Skills, Evaluate, Learn, Evolve)",
  "summary": "Validates the higher-order MCP tools that expose soul psychology — skill tracking, rubric-based evaluation, learning events, and the propose/approve/reject evolution workflow. Tests use FastMCP's in-process client to exercise the full MCP tool call path without a network round-trip.",
  "concepts": [
    "soul_skills",
    "soul_evaluate",
    "soul_learn",
    "soul_evolve",
    "rubric scores",
    "evolution workflow",
    "propose approve reject",
    "skill acquisition",
    "learning event",
    "MCP tools",
    "FastMCP",
    "psychology layer"
  ],
  "categories": [
    "testing",
    "MCP",
    "psychology tools",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "3a8ee2e88c243da4"
  ],
  "backlinks": null,
  "word_count": 583,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_psychology_tools.py` validates the psychology-layer MCP tools that sit above basic memory operations. While `test_server.py` covers CRUD-level soul tools (birth, remember, recall), this file tests tools that model the soul's growth and self-assessment: skills it has developed, rubric scores from evaluations, learning events, and identity mutations through the evolution system.

## soul_skills (TestSoulSkills)

The `soul_skills` tool surfaces the soul's acquired capability set:

- **Fresh soul returns empty list** — a newly born soul has no skills yet; this prevents the skill list from being pre-populated with default values
- **Returns soul name** — the response envelope always includes the target soul's name for disambiguation
- **After observe may gain skills** — after processing interaction turns via `soul_observe`, the skill list may grow (not guaranteed — depends on content), verifying the skill-acquisition pipeline is wired
- **Schema validation** — the tool's JSON Schema is well-formed and matches the expected input shape
- **Named soul targeting** — calling with an explicit `name` param targets a specific soul without switching the active soul
- **Raises without soul** — calling with no loaded soul raises a structured error, not an unhandled exception

## soul_evaluate (TestSoulEvaluate)

Rubric-based evaluation scores the soul against defined criteria:

- **Returns rubric scores** — the response contains per-criterion score values
- **Criterion schema** — each score entry has the expected fields (criterion name, score, rationale)
- **Increments history** — repeated evaluations accumulate an evaluation history (supports trend analysis)
- **Domain parameter** — an optional `domain` argument scopes evaluation to a specific capability area
- **Returns learning_field** — the evaluation result includes a `learning_field` that summarizes growth opportunities, not just scores

## soul_learn (TestSoulLearn)

`soul_learn` triggers an explicit learning event (distinct from passive learning through `soul_observe`):

- **Returns soul name** in the response envelope
- **Returns learning event or None** — learning may not always produce a structured event (depends on content richness); the tool must handle both cases without error
- **Learning event schema** — when present, the event has expected fields (content, domain, impact)
- **Domain param** — scopes the learning to a specific area

## soul_evolve (TestSoulEvolve)

The evolution tool implements a propose → approve/reject workflow for identity mutations:

```
list (empty) → propose → list (shows pending) → approve/reject → list (cleared)
```

Key tests:
- **Empty on fresh soul** — no pending mutations at birth
- **Propose creates pending mutation** — after proposing, the mutation appears in the pending list
- **Approve flow** — approval applies the mutation and clears it from pending
- **Approve clears pending** — post-approval, the list returns to empty (idempotency guard)
- **Reject flow** — rejection discards the mutation without applying it
- **Propose schema** — the proposal response has the expected fields

The propose/approve/reject pattern exists to prevent unbounded autonomous identity drift. A soul cannot mutate its own identity without an explicit approval step — this is a safety gate against runaway self-modification.

## Why In-Process Testing with FastMCP

These tests use FastMCP's test client to call tools in-process rather than spinning up a real MCP server. This eliminates network latency and process management overhead while still exercising the full tool registration and dispatch path. The tradeoff is that transport-layer bugs (JSON serialization errors, connection handling) are not caught here.

## Known Gaps

No TODOs flagged. The `test_soul_skills_after_observe_may_gain_skills` test is non-deterministic by design (skills may or may not appear depending on observe content) — this is noted as acceptable but could produce intermittent false negatives if the observe content is unexpectedly rich.