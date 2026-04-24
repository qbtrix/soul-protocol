---
{
  "title": "Evolution Manager: DNA Mutation Lifecycle",
  "summary": "`EvolutionManager` orchestrates the full lifecycle of soul personality mutations — proposal, approval/rejection, and application to DNA — across three modes: disabled, supervised, and autonomous. It is the core mechanism by which souls evolve over time based on interaction performance.",
  "concepts": [
    "EvolutionManager",
    "DNA mutation",
    "propose",
    "approve",
    "reject",
    "apply",
    "EvolutionMode",
    "supervised",
    "autonomous",
    "immutable traits",
    "check_triggers",
    "Mutation",
    "deep copy DNA"
  ],
  "categories": [
    "evolution",
    "DNA",
    "soul-lifecycle",
    "governance"
  ],
  "source_docs": [
    "47f6ab39ada07668"
  ],
  "backlinks": null,
  "word_count": 427,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Souls in Soul Protocol are not static. Their personality traits (warmth, curiosity, assertiveness, etc.) can change over time based on how the soul performs. `EvolutionManager` is the gate through which every change to a soul's DNA must pass. It enforces governance rules (which traits can mutate, who approves), tracks history, and applies approved changes safely.

## Three Evolution Modes

```python
class EvolutionMode(Enum):
    DISABLED    # mutations raise ValueError
    SUPERVISED  # mutations go to pending queue, require explicit approval
    AUTONOMOUS  # mutations auto-approve on proposal
```

Most production souls run in `SUPERVISED` mode: the system can propose changes, but a human (or governance layer) approves them. `AUTONOMOUS` is suitable for experimental souls or rapid iteration. `DISABLED` locks a soul's DNA permanently — useful for governance souls that must not drift.

## Mutation Lifecycle

### Proposal

```python
async def propose(dna, trait, new_value, reason) -> Mutation
```

Reads the current trait value from DNA via dot-notation (`communication.warmth`), creates a `Mutation` record with a 12-char UUID, and either auto-approves it (autonomous) or queues it pending (supervised).

**Immutability guard:** if the top-level trait category (e.g., `"core"`) is listed in `EvolutionConfig.immutable_traits`, the proposal raises `ValueError` before any state changes.

### Approval / Rejection

```python
async def approve(mutation_id) -> bool
async def reject(mutation_id) -> bool
```

Both methods search the pending list for the mutation by ID, update `approved`, move it from `pending` to `history`, and log the action. A missing mutation ID returns `False` without raising — callers must check the return value.

### Application

```python
def apply(dna, mutation_id) -> DNA
```

Critically, `apply()` does **not** mutate the input DNA. It creates a deep copy via `DNA.model_dump()` → `DNA.model_validate()` round-trip, then sets the new value. This ensures the original DNA is preserved until the application is explicitly committed. The type coercion in `_set_nested_attr` preserves the original field type: a float trait receives a float, not a string.

### Persistence Fix

An earlier version stored pending mutations in an in-memory list. After a save/reload cycle, pending mutations would disappear. The fix was to store them in `EvolutionConfig.pending` (a Pydantic model field that gets serialized), so they survive the `.soul` archive round-trip.

## Trigger-Driven Evolution

```python
async def check_triggers(dna, interaction, evaluation_triggers) -> list[Mutation]
```

Accepts output from `Evaluator.check_evolution_triggers()`. For each `"high_performance_streak"` trigger, proposes increasing `communication.warmth` to `"high"`. This wires evaluation scores directly to DNA changes without manual intervention.

## Known Gaps

- Only `communication.warmth` is proposed in `check_triggers()`. A richer trigger-to-trait mapping would let different domains drive different trait changes.
- No rate limiting on proposals: a runaway evaluator could flood the pending queue.