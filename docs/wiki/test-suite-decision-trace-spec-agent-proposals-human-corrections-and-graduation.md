---
{
  "title": "Test Suite: Decision Trace Spec — Agent Proposals, Human Corrections, and Graduation",
  "summary": "Validates the decision-trace spec from Workstream D of the Org Architecture RFC, covering the three payload types (`AgentProposal`, `HumanCorrection`, `DecisionGraduation`), their JSON round-trips, field validation, and the builder helpers that emit correctly shaped `EventEntry` records to the org journal.",
  "concepts": [
    "AgentProposal",
    "HumanCorrection",
    "DecisionGraduation",
    "disposition Literal",
    "confidence validation",
    "ACTION_NAMESPACES",
    "build_proposal_event",
    "build_correction_event",
    "find_corrections_for",
    "trace_decision_chain",
    "cluster_correction_patterns",
    "org journal",
    "audit trail"
  ],
  "categories": [
    "testing",
    "decision tracing",
    "org architecture",
    "audit",
    "test"
  ],
  "source_docs": [
    "6d3bf4bf9bbea2b2"
  ],
  "backlinks": null,
  "word_count": 515,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The decision-trace spec answers a key auditing question: when an AI agent proposes an action and a human corrects it, how is that interaction recorded in a way that can be queried later? This test file locks the data contracts that power that audit trail — the payload models, their validation rules, and the builder functions that turn them into journal events.

## AgentProposal

```python
proposal = AgentProposal(
    proposal_kind="message_draft",
    summary="Draft reply to Acme's pricing question.",
    proposal={"to": "buyer@acme.com", "body": "Thanks for reaching out..."},
    confidence=0.72,
    alternatives=[{"body": "Shorter variant."}],
    context_refs=[uuid4(), uuid4()],
)
```

Key validation rules tested:
- **confidence is optional**: Omitting it is valid (`confidence is None`)
- **context_refs defaults to `[]`**: Empty list, not None — prevents callers from having to handle both
- **confidence must be in `[0.0, 1.0]`**: Values like `1.5` raise `ValidationError`. This enforces that confidence is a probability, preventing accidental use of percentage values (e.g., `72` instead of `0.72`)

## HumanCorrection

`HumanCorrection` records what a human reviewer did with a proposal:

- `disposition`: A `Literal` field — only accepted values (`"edited"`, `"approved"`, `"rejected"`, etc.) are valid. Unknown values raise `ValidationError`, preventing typos from silently creating unrecognized disposition states.
- `corrected_value` is `None` when `disposition="rejected"`: A rejected proposal has no corrected value. Testing this explicitly prevents code that always populates `corrected_value` from breaking rejected-proposal queries.
- `edit_distance` is optional: Some correction workflows compute text edit distance; others do not. Optional fields survive round-trips as `None`.
- `structured_reason_tags`: A list of categorized reason codes that enable `cluster_correction_patterns()` to identify systemic issues.

## DecisionGraduation

Graduation marks when a proposal has been reviewed enough times to be considered a standing decision:

```python
proposal = AgentProposal(...)
decision = DecisionGraduation(supporting_ids=[uuid4()])
```

`supporting_ids` is required and must be non-empty — a graduation without supporting evidence is rejected. This enforces that the spec cannot produce undocumented decisions.

## Action Namespaces

```python
def test_namespaces_include_decision_actions():
    assert "decision:propose" in ACTION_NAMESPACES
    assert "decision:correct" in ACTION_NAMESPACES
```

`ACTION_NAMESPACES` is the registry of valid action strings for `EventEntry.action`. Testing that decision actions are registered prevents the spec from producing events with actions that are unrecognized by the namespace registry.

## Builder Helpers

`build_proposal_event(drafter, proposal)` and `build_correction_event(reviewer, correction)` produce `EventEntry` objects for the journal. Tests assert the correct structure:
- The `actor` field matches the `drafter`/`reviewer` fixture
- The `action` is `"decision:propose"` or `"decision:correct"`
- The `payload` contains the serialized proposal/correction

These builder tests prevent the helpers from emitting events with wrong action strings or missing payload fields, which would corrupt the audit trail.

## Querying Helpers

The module also exports `find_corrections_for`, `trace_decision_chain`, and `cluster_correction_patterns` — tested by the AST structure but not shown in the source excerpt. Their docstrings note that `find_corrections_for` filters on `causation_id` (not `correlation_id`), a precision detail that prevents returning unrelated events from the same conversation.

## Known Gaps

The source is created under `feat/decision-traces` (Workstream D, PR #164), which suggests this is a recent addition. No TODO or FIXME markers, but the `cluster_correction_patterns(min_occurrences=...)` parameter behavior is mentioned in the file header without a test visible in the excerpt — it may be tested in the full source but not shown.