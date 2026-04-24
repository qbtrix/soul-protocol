---
{
  "title": "Test Suite: Multi-Participant Interactions and Multi-Bond Identity",
  "summary": "Tests for the multi-participant Interaction model (issue #95) and multi-bond Identity (issue #94), including full backward compatibility with the legacy user_input/agent_output API, serialization round-trips, and coverage of the spec-layer equivalents.",
  "concepts": [
    "Participant",
    "multi-participant",
    "Interaction",
    "BondTarget",
    "multi-bond",
    "Identity",
    "backward compatibility",
    "from_pair",
    "user_input",
    "agent_output",
    "soul-to-soul",
    "spec layer"
  ],
  "categories": [
    "data-models",
    "testing",
    "backward-compatibility",
    "identity",
    "test"
  ],
  "source_docs": [
    "54e32be9aaac7c3e"
  ],
  "backlinks": null,
  "word_count": 422,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Multi-Participant Interactions and Multi-Bond Identity

`test_multi_participant.py` validates two related schema extensions: multi-participant `Interaction` (issue #95) and multi-bond `Identity` (issue #94). Both features expand soul-protocol beyond the original one-user / one-agent assumption to support group conversations, soul-to-soul interactions, and an AI companion that maintains bonds with multiple people.

### Why Multi-Participant?

The original `Interaction` model had `user_input: str` and `agent_output: str` — a hard assumption of exactly one human and one AI. Real deployments encounter group chats, system messages injected by platforms, and soul-to-soul peer interactions. The new `participants: list[Participant]` field accommodates any number of roles.

### Participant Model

```python
p = Participant(role="user", content="hello")
p = Participant(role="agent", id="did:key:agent-001", content="hi there")
p = Participant(role="system", content="context")
```

`TestParticipant` verifies the three-field model (role, content, optional id), default `id=None`, and serialization round-trip via `model_dump()` / `model_validate()`.

### Backward Compatibility (TestInteractionBackwardCompat)

The legacy constructor API must continue to work:

```python
# Old API — still valid
Interaction(user_input="hello", agent_output="hi")
```

Tests verify:
- Legacy constructor populates `participants` automatically (creating user + agent entries)
- `channel` and `metadata` kwargs still accepted
- `user_input`-only and `agent_output`-only interactions create the appropriate single participant
- Legacy properties (`interaction.user_input`, `interaction.agent_output`) still work as computed properties

This is critical: any code using the old API must not require changes.

### New Multi-Participant API (TestInteractionMultiParticipant)

```python
# New factory method
Interaction.from_pair(user="Alice said hi", agent="Hello Alice", channel="slack")

# Arbitrary participants
Interaction(participants=[
    Participant(role="user", content="..."),
    Participant(role="user", content="..."),  # second user
    Participant(role="agent", content="..."),
])
```

Edge cases tested: three-participant conversations, system participant injection, no user participant, no agent participant, empty participants list, and soul-to-soul interactions (both roles are agents).

A key guard: `test_legacy_does_not_overwrite_explicit_participants` — if both `user_input` and an explicit `participants` list are provided, the explicit list wins. This prevents the auto-population logic from clobbering intentionally constructed participant lists.

### BondTarget and Multi-Bond Identity

Issue #94 extends `Identity.bonds: list[BondTarget]` to replace the single `bonded_to` string:

```python
BondTarget(id="did:key:abc", type="human", label="Alice")
```

`TestIdentityMultiBond` verifies:
- Fresh `Identity` has no bonds (`bonds == []`)
- Multiple bond targets of different types coexist
- Auto-migration: `bonded_to="did:key:abc"` with no `bonds` creates a `BondTarget` automatically
- No migration when `bonds` is already set
- JSON round-trip preserves all bond fields

### Spec-Layer Equivalents

`TestCoreParticipant`, `TestCoreInteraction`, `TestCoreBondTarget` mirror the runtime tests against `soul_protocol.spec.*` models, confirming that the spec layer (used for `.soul` file format) and the runtime layer stay synchronized.

### Known Gaps

No test covers serializing an interaction with mixed legacy and multi-participant fields to the `.soul` file format and reading it back on a version that only understands the legacy format.
