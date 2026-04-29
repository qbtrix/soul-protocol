---
{
  "title": "Decision Trace Models: Structured Agent Proposal and Human Correction Events",
  "summary": "`spec/decisions.py` defines the payload types and helpers for the Org Journal's decision trace workstream — structuring every agent proposal, human correction, and pattern graduation as auditable, linkable `EventEntry` pairs. The module enables agents to learn from correction patterns without requiring ad-hoc feedback loops.",
  "concepts": [
    "AgentProposal",
    "HumanCorrection",
    "DecisionGraduation",
    "Disposition",
    "decision traces",
    "causation_id",
    "correlation_id",
    "EventEntry",
    "structured_reason_tags",
    "cluster_correction_patterns",
    "graduation",
    "Org Journal"
  ],
  "categories": [
    "spec",
    "decision tracing",
    "agent learning",
    "auditing"
  ],
  "source_docs": [
    "a53cd9fcf05ef6c2"
  ],
  "backlinks": null,
  "word_count": 555,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Every time an agent proposes an action and a human edits, accepts, rejects, or defers it, that pair of events is a structured learning signal. `spec/decisions.py` formalizes this pattern into three payload models (`AgentProposal`, `HumanCorrection`, `DecisionGraduation`) and five helper functions that build, query, and cluster these events in the Org Journal.

This module is Workstream D of the Org Architecture RFC (PR #164) and represents one of the four "compounding data types" identified in the Paw OS gaps analysis — data that becomes more valuable over time through accumulation.

## The Three Event Types

### AgentProposal

The agent's proposed action, structured for field-level alignment with the human's eventual correction:

```python
AgentProposal(
    proposal_kind="message_draft",    # tool_call | message_draft | decision | custom:*
    summary="Draft reply to Q3 budget inquiry.",
    proposal={"subject": "Re: Q3", "body": "..."},
    confidence=0.85,
    alternatives=[{"body": "..."}],   # options the agent considered but did not surface
    context_refs=[uuid4()],            # prior EventEntry IDs the agent consulted
)
```

`proposal_kind` is a free-form string, not an enum — the taxonomy is a convention, not a schema constraint. This prevents the spec from ossifying around a fixed list as new agent capabilities emerge. The `custom:` prefix is the extension point for domain-specific proposal types.

`context_refs` grounds the proposal in the journal: a reviewer can inspect exactly which prior decisions and retrievals the agent consulted when drafting the proposal. This is critical for auditing and debugging systematic errors.

### HumanCorrection

Linked to the proposal via `causation_id` in the parent `EventEntry`:

```python
HumanCorrection(
    disposition="edited",                        # accepted | edited | rejected | deferred
    corrected_value={"body": "..."},              # final value after human edit
    correction_reason="Too formal for internal mail.",
    structured_reason_tags=["tone_too_formal"],   # machine-readable for clustering
    edit_distance=0.3,                            # 0.0 = identical, 1.0 = completely different
)
```

`disposition` is a `Literal` — unknown values raise a `ValidationError` immediately, preventing silent misclassification. The four dispositions cover the full decision space: the agent was right (`accepted`), partially right (`edited`), wrong (`rejected`), or the decision is deferred to a later time.

`structured_reason_tags` is the key machine-readable signal. Teams should maintain a small, stable vocabulary per pocket (e.g., `["tone_too_formal", "wrong_recipient", "missed_context"]`) to keep `cluster_correction_patterns()` results meaningful.

### DecisionGraduation

When a correction pattern recurs often enough, it graduates from episodic to semantic (or core) memory:

```python
DecisionGraduation(
    pattern_summary="Use first names, not titles, for internal replies.",
    supporting_correction_ids=[uuid1, uuid2, uuid3],
    graduated_to_tier="semantic",
    confidence=0.9,
    applies_to={"channel": "email", "recipients": "internal"},
)
```

`supporting_correction_ids` provides auditability: a reviewer can trace exactly which human corrections were used to derive the graduated rule.

## Builder Helpers

`build_proposal_event` and `build_correction_event` wrap payload models into properly structured `EventEntry` instances:

```python
proposal_evt = build_proposal_event(
    actor=agent_actor, scope=["org:sales"],
    correlation_id=corr_id, proposal=proposal
)
correction_evt = build_correction_event(
    actor=human_actor, scope=["org:sales"],
    correlation_id=corr_id, causation_id=proposal_evt.id,
    correction=correction
)
```

The `causation_id` linkage is what makes the proposal/correction pair queryable as a unit.

## Query and Clustering Helpers

- **`find_corrections_for(journal, proposal_id)`** — all `human.corrected` events for a given proposal (a proposal may have multiple corrections: deferral then acceptance).
- **`trace_decision_chain(journal, correlation_id)`** — full ordered chain of proposal/correction/graduation events for a workflow.
- **`cluster_correction_patterns(journal, min_occurrences=3)`** — groups corrections by `structured_reason_tags` tuple and returns clusters meeting the occurrence threshold. These are graduation candidates.

## Known Gaps

The graduation promotion logic — actually moving a `DecisionGraduation` event's `pattern_summary` into semantic or core memory — is explicitly deferred to a later PR. `cluster_correction_patterns` surfaces candidates only. Richer clustering (embedding-based, tag-hierarchy-aware) is flagged as a future enhancement in the source comments.