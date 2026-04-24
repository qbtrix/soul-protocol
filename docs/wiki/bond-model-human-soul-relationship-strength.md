---
{
  "title": "Bond Model: Human-Soul Relationship Strength",
  "summary": "Models the trust relationship between a human and their soul companion, tracking bond strength and interaction count. Uses logarithmic growth to make early bonding feel natural while making deep trust genuinely hard-earned through sustained interaction.",
  "concepts": [
    "bond strength",
    "logarithmic growth",
    "trust",
    "relationship",
    "memory visibility",
    "interaction count",
    "time decay",
    "DID",
    "BONDED memory",
    "PRIVATE memory",
    "BondTarget",
    "multi-participant"
  ],
  "categories": [
    "runtime",
    "identity",
    "memory",
    "psychology"
  ],
  "source_docs": [
    "52dbb6d2dfec4ce3"
  ],
  "backlinks": null,
  "word_count": 434,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `Bond` model is the soul's representation of its relationship with a specific human. Bond strength is not just a cosmetic metric — it gates memory visibility. Higher bond levels unlock `BONDED` and `PRIVATE` memory tiers, so the soul only reveals sensitive context to humans who have earned trust through many interactions.

## Data Model

```python
class Bond(BaseModel):
    bonded_to: str = ""          # Human's DID or identifier
    bonded_at: datetime = ...    # When the relationship began
    bond_strength: float = 50.0  # 0-100, evolves over time
    interaction_count: int = 0
```

The `ge=0, le=100` validators on `bond_strength` ensure the value is always in range at the Pydantic level, preventing invalid state from being persisted to disk.

## Strengthen: Logarithmic Growth

```python
def strengthen(self, amount: float = 1.0) -> None:
    remaining = 100.0 - self.bond_strength
    effective = amount * (remaining / 100.0)
    self.bond_strength = min(100.0, self.bond_strength + effective)
    self.interaction_count += 1
```

At `bond=50`, each interaction contributes `1.0 * 0.5 = 0.5` points. At `bond=90`, it contributes only `1.0 * 0.1 = 0.1` points. Reaching 99 from 50 takes approximately 460 interactions.

This logarithmic curve was introduced in the `phase1-ablation-fixes` update to address a problem with linear growth: linear accumulation made deep trust trivially achievable in short automated sessions, which broke the intended semantics of `PRIVATE` memory visibility.

## Weaken: Linear Decay

```python
def weaken(self, amount: float = 0.5) -> None:
    self.bond_strength = max(0.0, self.bond_strength - amount)
```

Weakening is linear and immediate. This asymmetry is intentional: trust is slow to build but can be damaged quickly. Time decay (called by the soul engine periodically) uses this method, as do explicit negative interaction signals.

## Multi-Bond Architecture

The `Bond` model is per-relationship. The `Identity` model holds a list of `BondTarget` entries for multi-participant scenarios. The Bond model itself has no knowledge of this — it simply tracks the relationship with the specific `bonded_to` entity.

## Logging

Structured `logger.debug()` calls capture bond strength and interaction count on each strengthen operation. This makes it possible to trace bond evolution in logs without modifying the model.

## Data Flow

1. `Soul.observe(interaction)` calls `bond.strengthen()` after a positive interaction.
2. `soul_bond` MCP tool exposes `bond_strength` and `interaction_count` to agents.
3. Memory retrieval checks `bond_strength` against tier thresholds before returning `BONDED` or `PRIVATE` memories.

## Known Gaps

- No explicit time-decay scheduling in this module — the caller is responsible for calling `weaken()` on a schedule. There is no built-in cron or background task here.
- `bonded_to` is a free-form string (DID or any identifier). No validation that it matches a real DID format is performed at the Bond level.