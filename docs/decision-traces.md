<!--
decision-traces.md — Concept doc for the decision-trace event chain.
Created: feat/decision-traces — Workstream D of Org Architecture RFC (PR #164).
Pairs with src/soul_protocol/spec/decisions.py and tests/test_spec/test_decisions.py.
-->

# Decision Traces

> Every agent proposal a human edits, accepts, rejects, or defers becomes a
> structured, auditable, replayable pair of events in the org journal. Over
> time, recurring corrections graduate into standing guidance the agent
> loads as memory.

This is one of the four compounding data types that differentiate Paw OS
from generic stack-of-record systems. Decisions are not built in SAP or
Salesforce. They are built here.

---

## The three event types

A decision trace is a chain of journal events linked by `causation_id`:

1. **`agent.proposed`** — payload: [`AgentProposal`](../src/soul_protocol/spec/decisions.py)
   The agent emits a structured proposal: a tool call, a draft message, or
   a decision among options. The proposal carries a one-to-three sentence
   summary, the structured payload, an optional self-reported confidence,
   the alternatives the agent considered, and references to prior journal
   events the agent consulted (`context_refs`).

2. **`human.corrected`** — payload: [`HumanCorrection`](../src/soul_protocol/spec/decisions.py)
   A reviewer dispositions the proposal — `accepted`, `edited`, `rejected`,
   or `deferred`. The event's `causation_id` points at the
   `agent.proposed` event. `structured_reason_tags` (e.g.
   `tone_too_formal`, `wrong_recipient`) carry the *why* in a form the
   graduation pipeline can cluster on.

3. **`decision.graduated`** — payload: [`DecisionGraduation`](../src/soul_protocol/spec/decisions.py)
   When a pattern of corrections recurs, the system promotes it from
   episodic memory (the raw correction events) to semantic or core memory
   (standing guidance the agent reads on every relevant turn). The payload
   carries the pattern summary, the supporting correction ids (so the
   rule is auditable), the target tier, and the scope it applies to.

---

## Example flow

The sales agent at Acme drafts a reply to a buyer:

```text
ts=T0  action=agent.proposed       payload=AgentProposal(kind="message_draft",
                                                         summary="Reply to pricing question",
                                                         proposal={...})
ts=T1  action=human.corrected      causation_id=<T0.id>
                                   payload=HumanCorrection(disposition="edited",
                                                           corrected_value={...},
                                                           structured_reason_tags=["tone_too_formal"])
```

Ten similar corrections accumulate over a month. The graduation pipeline
spots the cluster:

```text
ts=T_n  action=decision.graduated   payload=DecisionGraduation(
                                       pattern_summary="Use casual register for replies to existing buyers",
                                       supporting_correction_ids=[<10 uuids>],
                                       graduated_to_tier="semantic",
                                       confidence=0.91,
                                       applies_to={"channel": "email", "stage": "post-sale"})
```

From that point on the agent loads the rule as memory — and the team
stops having to make the same edit.

---

## Why this matters vs. raw training data

- **Structured.** Every correction carries a disposition and a small set of
  reason tags from a closed vocabulary. Cluster-able by construction. No
  vibes-based "the agent should just sound more like us."
- **Auditable.** Every graduated rule cites the corrections it was drawn
  from. A reviewer can trace any standing rule back to the raw events,
  decide it's wrong, and demote it.
- **Org-scoped.** Events carry DSP scope tags. A rule learned in
  `org:sales:pocket:acme` does not bleed into `org:engineering`.
- **Replayable.** Because the journal is append-only with monotonic
  timestamps, the entire decision history can be replayed against a new
  graduation policy without losing fidelity.

---

## Programming surface

The spec ships three Pydantic models and four helpers in
[`soul_protocol.spec.decisions`](../src/soul_protocol/spec/decisions.py):

| Helper | Purpose |
|---|---|
| `build_proposal_event(actor, scope, correlation_id, proposal)` | Construct the `agent.proposed` `EventEntry` with the right action and serialized payload. |
| `build_correction_event(actor, scope, correlation_id, causation_id, correction)` | Same for `human.corrected`, with the required link to the prior proposal. |
| `find_corrections_for(journal, proposal_id)` | List every `human.corrected` event whose `causation_id` is `proposal_id`. |
| `trace_decision_chain(journal, correlation_id)` | Return the time-ordered proposal/correction events for a session or flow. |
| `cluster_correction_patterns(journal, since=..., min_occurrences=3)` | Surface candidate graduation patterns by tag co-occurrence. Promotion logic itself ships in a follow-up slice. |

The pocketpaw runtime wires these into the tool-preview UI and the draft
approval flow — that integration lands in a follow-up PR in the
`pocketpaw` repo, not here.

---

## What's deliberately not in this slice

- **Promotion logic.** `cluster_correction_patterns` *surfaces* candidate
  patterns. The actual write of `decision.graduated` events, plus the
  policy for picking `semantic` vs `core`, is future work.
- **Embedding-based clustering.** Today's clustering is exact match on the
  sorted tag tuple. Richer schemes (tag hierarchies, embedding-similarity
  on `correction_reason`) are intentional next steps.
- **Edit-distance scoring.** The field is on the model (`HumanCorrection.edit_distance`)
  but no scorer is bundled — consumers compute the score they want and
  attach it.

See [RFC PR #164](https://github.com/qbtrix/soul-protocol/pull/164) and
the [org architecture doc](./org-architecture.md) for the larger context.
