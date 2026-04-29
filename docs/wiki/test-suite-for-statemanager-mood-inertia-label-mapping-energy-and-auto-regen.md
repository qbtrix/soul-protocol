---
{
  "title": "Test Suite for StateManager: Mood Inertia, Label Mapping, Energy, and Auto-Regen",
  "summary": "This test suite covers the `StateManager` component responsible for tracking a soul's emotional and physical state across interactions. It validates EMA-based mood inertia, label-to-mood mapping, the TIRED energy override, and the fully configurable `Biorhythms` parameter set including time-based auto-regeneration — with a particular focus on preventing mood instability and ensuring always-on agent deployments work correctly.",
  "concepts": [
    "StateManager",
    "mood inertia",
    "EMA",
    "Biorhythms",
    "energy drain",
    "social battery",
    "TIRED override",
    "auto-regen",
    "label-to-mood mapping",
    "somatic marker",
    "always-on agent"
  ],
  "categories": [
    "testing",
    "state-management",
    "emotional-state",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "77347fe8e0764571"
  ],
  "backlinks": null,
  "word_count": 547,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`StateManager` is the component that updates a soul's `SoulState` (mood, energy, social battery) in response to each `Interaction`. The state system has two independent layers: somatic signals (emotional content detected from interactions) and biorhythmic resources (energy and social battery that drain over time). This test file was created to address two specific production bugs: a mood that flipped too easily on a single mildly negative message, and a missing label-to-mood lookup dictionary.

## Mood Inertia via EMA

### The Problem

Without inertia, a single negative interaction could instantly flip a companion from NEUTRAL to CONCERNED or CONTEMPLATIVE. This produced jarring UX where one user complaint would visibly change the AI's demeanor.

### The Fix: Exponential Moving Average

Mood updates now use an EMA over incoming valence signals:

```
ema = alpha * valence + (1 - alpha) * ema_prev
```

A mood shift only fires when `abs(ema) > threshold`. With default `alpha=0.4` and `threshold=0.25`, a single `valence=-0.3` produces `ema=-0.12` — below threshold, no shift:

```python
manager.on_interaction(interaction, somatic=_make_somatic(valence=-0.3, arousal=0.6, label="sadness"))
assert manager.current.mood == Mood.NEUTRAL
```

But accumulation across multiple interactions does eventually shift mood, which is the expected behavior for persistent emotional context.

### Reset Clears History

`reset()` zeroes the EMA so negative history from a previous session does not bleed into the next:

```python
manager.reset()
# Fresh EMA from 0 — strong positive now shifts correctly
assert manager.current.mood == Mood.EXCITED
```

## Label-Based Mood Mapping

The `_LABEL_TO_MOOD` dictionary maps NLP sentiment labels to `Mood` enum values, bypassing the valence/arousal quadrant fallback:

```python
("excitement", 0.8, Mood.EXCITED),
("sadness",    0.1, Mood.CONTEMPLATIVE),
("confusion",  0.5, Mood.FOCUSED),
```

The test `test_all_label_to_mood_keys_covered` iterates the entire dictionary and asserts every value is a `Mood` instance, catching copy-paste errors where a label was added but mapped to a string.

## Energy and Social Battery

### Configurable Biorhythms

All drain rates, thresholds, and regen parameters are injected via the `Biorhythms` dataclass:

```python
bio = Biorhythms(energy_drain_rate=5.0, auto_regen=False)
manager = StateManager(_make_state(), biorhythms=bio)
manager.on_interaction(_make_interaction())
assert manager.current.energy == pytest.approx(95.0)
```

This enables the **always-on agent preset** where all drain rates and the tired threshold are set to zero, making energy and mood fully stable for long-running autonomous agents.

### TIRED Override

When `energy < tired_threshold`, the mood is forced to `Mood.TIRED` regardless of somatic signals. This prevents a companion from appearing energized when its resources are depleted. Setting `tired_threshold=0.0` disables the override entirely.

## Time-Based Auto-Regen

When `auto_regen=True`, each interaction first applies regeneration proportional to the elapsed time since the last interaction:

```python
# 2 hours at 10/hr → +20 energy before next drain
manager.on_interaction(_make_interaction_at(t2))
expected = energy_after_first + 20.0 - 2.0
assert manager.current.energy == pytest.approx(expected)
```

Key behaviors tested:
- Auto-regen is **skipped on the very first interaction** (no prior timestamp to delta against).
- Two interactions at the **same timestamp** produce zero regen.
- Energy is **clamped at 100** regardless of elapsed time.
- `rest(hours=n)` uses `biorhythms.energy_regen_rate`, not a hardcoded value.

## Known Gaps

- Social battery regen rate is hard-coded as half the energy regen rate — there is no `social_regen_rate` parameter in `Biorhythms` yet.
- The TIRED override does not have a recovery path — once energy drops below the threshold, only `rest()` can clear TIRED, not somatic signals.
- Concurrent `on_interaction` calls (multithreaded agents) are not tested for race conditions on the EMA state.