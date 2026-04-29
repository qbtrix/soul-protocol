---
{
  "title": "StateManager: Runtime Soul State and Mood Dynamics",
  "summary": "`StateManager` owns all mutable runtime state for a digital soul — energy, social battery, mood, and interaction timestamps. It provides delta-based updates, time-based auto-regeneration, and EMA-smoothed mood transitions driven by somatic markers from the sentiment pipeline.",
  "concepts": [
    "StateManager",
    "SoulState",
    "Biorhythms",
    "mood inertia",
    "EMA",
    "somatic marker",
    "energy drain",
    "auto-regeneration",
    "tired threshold",
    "delta update",
    "valence",
    "arousal"
  ],
  "categories": [
    "runtime",
    "state management",
    "mood dynamics"
  ],
  "source_docs": [
    "698af1091427c625"
  ],
  "backlinks": null,
  "word_count": 450,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`StateManager` is the single authority for mutating a soul's live state. It wraps a `SoulState` Pydantic model and a `Biorhythms` config, exposing a verb-oriented API: `update()`, `on_interaction()`, `rest()`, and `reset()`. All behavioral parameters are externalized to `Biorhythms` — no magic numbers live in this class.

## Core Mechanics

### Delta-Based Updates

`update(**kwargs)` treats `energy` and `social_battery` as deltas, not setpoints:

```python
manager.update(energy=-10)       # decrease by 10
manager.update(social_battery=5) # increase by 5
manager.update(mood=Mood.TIRED)  # direct set for non-numeric fields
```

Both fields are clamped to `[0, 100]` after every operation. This prevents an accidental setpoint write from pushing energy to an invalid value.

### EMA-Smoothed Mood Transitions

A single emotional message should not flip a soul's mood. `on_interaction()` runs somatic markers through an exponential moving average (EMA) of valence:

```python
alpha = self._bio.mood_inertia  # 0 = max inertia, 1 = instant
self._valence_ema = alpha * somatic.valence + (1 - alpha) * self._valence_ema
```

The smoothed signal feeds `_somatic_to_mood()`, which first tries a label-based lookup (labels were already resolved by `sentiment.py`) and falls back to valence/arousal quadrant math for custom markers. This avoids re-computing quadrant logic the sentiment pipeline already handled.

### Time-Based Auto-Regeneration

`_apply_auto_regen()` recovers energy proportional to elapsed time since the last interaction. It runs *before* the drain in `on_interaction()` — by design, because it uses the old `last_interaction` timestamp. Running it after drain would compute zero elapsed time and skip regen entirely.

The method handles timezone-naive datetimes defensively by attaching `UTC` when needed, preventing `TypeError` when comparing naive and aware datetimes.

### Low-Energy Override

When energy drops below `biorhythms.tired_threshold`, mood is forced to `TIRED` regardless of what the somatic pipeline computed. This models the real effect of fatigue overriding emotional content.

## Data Flow

```
Interaction + optional SomaticMarker
  → _apply_auto_regen(timestamp)     # recover before draining
  → update(energy=-drain, social_battery=-drain)
  → update last_interaction
  → EMA(somatic.valence) → _somatic_to_mood() → update mood
  → tired_threshold check → override mood if needed
```

## Biorhythms Configuration

| Parameter | Effect |
|-----------|--------|
| `energy_drain_rate` | Energy lost per interaction |
| `social_drain_rate` | Social battery lost per interaction |
| `energy_regen_rate` | Energy recovered per hour |
| `auto_regen` | Enable time-based recovery |
| `mood_inertia` | EMA alpha (0 = max inertia, 1 = instant) |
| `mood_sensitivity` | Valence threshold to trigger mood shift |
| `tired_threshold` | Energy level that forces TIRED mood |

Defaults to `0` for all drain/regen rates — suitable for tool-use agents that do not simulate fatigue.

## Known Gaps

The `rest()` and `_apply_auto_regen()` methods share identical gain formulas (energy at full rate, social battery at half). This duplication is intentional but could be extracted to a helper if `Biorhythms` gains a separate `social_regen_rate` config field.