---
{
  "title": "Test Suite for Soul Evolution Manager",
  "summary": "Tests for `EvolutionManager`, which controls how a soul's DNA traits mutate over time across three modes: supervised, autonomous, and disabled. Covers the full mutation lifecycle — propose, approve, reject, apply — and guards against illegal mutations on immutable traits.",
  "concepts": [
    "EvolutionManager",
    "DNA",
    "mutation",
    "supervised mode",
    "autonomous mode",
    "disabled mode",
    "EvolutionConfig",
    "EvolutionMode",
    "propose",
    "approve",
    "reject",
    "apply",
    "immutable trait",
    "personality evolution",
    "soul identity"
  ],
  "categories": [
    "testing",
    "evolution",
    "soul-protocol",
    "identity",
    "test"
  ],
  "source_docs": [
    "5b2f635f713dd19b"
  ],
  "backlinks": null,
  "word_count": 350,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

A soul's personality is encoded in its `DNA` object as named traits (e.g. `communication.warmth`). The `EvolutionManager` mediates changes to these traits, ensuring that mutations go through an appropriate approval workflow. This test file verifies that all three evolution modes behave correctly and that safety rails hold.

## Fixtures

Three `EvolutionConfig` fixtures exercise each mode:

```python
@pytest.fixture
def supervised_config() -> EvolutionConfig:
    return EvolutionConfig(mode=EvolutionMode.SUPERVISED)

@pytest.fixture
def autonomous_config() -> EvolutionConfig:
    return EvolutionConfig(mode=EvolutionMode.AUTONOMOUS)

@pytest.fixture
def disabled_config() -> EvolutionConfig:
    return EvolutionConfig(mode=EvolutionMode.DISABLED)
```

A shared `dna` fixture provides a default `DNA` instance so each test starts from a clean slate.

## Evolution Modes

### Supervised Mode
`test_propose_supervised_creates_pending` — proposals land in `mgr.pending` with `approved=None`, waiting for explicit human sign-off. This prevents autonomous drift in production deployments where an operator must review personality changes.

### Autonomous Mode
`test_propose_autonomous_auto_approves` — proposals are immediately approved. Designed for sandboxed or experimental deployments where continuous self-improvement is acceptable without human checkpoints.

### Disabled Mode
`test_propose_disabled_raises` — calling `propose()` raises `ValueError`. This is the fail-safe: when evolution is disabled (e.g. for a locked character in a game), the manager must hard-reject any attempt to mutate DNA rather than silently succeed or queue the change.

## Mutation Lifecycle

```
propose() → pending (supervised) or approved (autonomous)
    ↓
approve() / reject()
    ↓
apply()  → DNA trait updated
```

- **`test_approve_mutation`** — `approve()` moves `approved` from `None` to `True`.
- **`test_reject_mutation`** — `reject()` marks `approved=False`, preserving the audit record without applying the change.
- **`test_apply_mutation_changes_dna`** — `apply()` actually writes the new value into the `DNA` object. Tested separately from approval to ensure the mutation isn't applied prematurely during the approval step.

## Immutable Trait Guard

`test_immutable_trait_blocked` verifies that proposing a mutation on a trait flagged as immutable raises `ValueError`. This guard prevents core identity traits (e.g. a soul's fundamental values) from being mutated even in autonomous mode, protecting character integrity.

## Known Gaps

- No tests for concurrent proposals on the same trait, which could cause last-writer-wins bugs.
- No tests for persistence/serialisation of the pending queue across manager restarts.
- No tests for the maximum number of pending mutations (memory exhaustion risk).