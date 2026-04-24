---
{
  "title": "Test Suite for the Human-Soul Bond Model",
  "summary": "This test suite validates the `Bond` model that tracks the relationship strength between a soul and its bonded human, covering construction defaults, logarithmic growth on `strengthen()`, floor/ceiling clamping on `weaken()`, and Pydantic validation of out-of-range `bond_strength` values.",
  "concepts": [
    "Bond model",
    "bond_strength",
    "logarithmic growth",
    "strengthen",
    "weaken",
    "interaction_count",
    "Pydantic validation",
    "relationship tracking",
    "soul companion"
  ],
  "categories": [
    "testing",
    "bond",
    "soul-identity",
    "test"
  ],
  "source_docs": [
    "a434edd31924a06f"
  ],
  "backlinks": null,
  "word_count": 432,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `Bond` model is a core piece of soul identity — it tracks how deep the relationship between an AI companion and its human is. `bond_strength` is a float in `[0, 100]` that grows through positive interactions and decays through absence or negative events.

This test suite was created 2026-03-06 and updated during `phase1-ablation-fixes` when the growth curve changed from linear to logarithmic.

## Construction Defaults (`TestBondCreation`)

```python
bond = Bond()
assert bond.bonded_to == ""
assert bond.bond_strength == 50.0
assert bond.interaction_count == 0
assert bond.bonded_at is not None
```

The default `bond_strength` of 50 represents a neutral starting point — neither strong nor weak. `bonded_at` is always set on construction (timestamp of when the bond was formed), enabling calculations of bond age.

## Logarithmic Growth (`TestStrengthen`)

The `strengthen()` method uses a logarithmic curve to prevent bonds from maxing out too quickly:

```
gain = amount * (current_strength / 100)
```

At `bond_strength=50`, a default `strengthen()` call (amount=1.0) adds `0.5`. At `bond_strength=99.5`, a call with amount=5.0 adds only `0.025`. This means early interactions build the bond rapidly while the final points toward 100 require sustained effort — modeling how real relationships work.

```python
# At bond=50: gain = 1.0 * (50/100) = 0.5 → new strength = 50.5
bond = Bond(bond_strength=50.0)
bond.strengthen()
assert bond.bond_strength == 50.5

# At bond=99.5, amount=5.0: gain = 5.0 * (0.5/100) = 0.025 → 99.525
bond = Bond(bond_strength=99.5)
bond.strengthen(5.0)
assert bond.bond_strength == pytest.approx(99.525)
```

Every `strengthen()` call increments `interaction_count`, regardless of how small the gain is. This counter is used elsewhere (e.g., in memory visibility rules).

## Floor/Ceiling Clamping (`TestWeaken`)

`weaken()` subtracts directly (no logarithmic curve — decay is linear):

```python
bond = Bond(bond_strength=0.3)
bond.weaken(1.0)
assert bond.bond_strength == 0.0  # floored at 0, not negative
```

The floor at 0 prevents nonsensical negative bond strengths. `weaken()` does not increment `interaction_count` — only positive interactions are tracked.

## Pydantic Bounds Validation (`TestBoundsValidation`)

```python
Bond(bond_strength=101.0)  # raises
Bond(bond_strength=-1.0)   # raises
Bond(bond_strength=0.0)    # valid
Bond(bond_strength=100.0)  # valid
```

Validation is at the model level (Pydantic), not in `strengthen()`/`weaken()`. This means invalid initial values are caught at construction time, while the methods handle clamping at runtime. The tests lock the boundary values exactly — 0 and 100 are valid, anything outside is not.

## Known Gaps

- There is no test for `strengthen()` when `bond_strength` is 0 (gain would be 0, making it impossible to grow from zero). This edge case likely requires a minimum gain floor in the implementation.
- The `bonded_to` field stores an arbitrary string; there is no validation that it is a valid DID or identifier format.