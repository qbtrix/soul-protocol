---
{
  "title": "Test Suite: Skills XP Progression, Level Cap, and Decay",
  "summary": "Validates the Skills subsystem — a gamification layer that tracks a soul's proficiency across named abilities via an XP and level model. The suite covers default construction, XP accumulation with level-up triggers, overflow carry, the level 10 cap, significance-weighted XP grants, skill decay, and the `SkillRegistry` collection.",
  "concepts": [
    "Skill",
    "SkillRegistry",
    "XP progression",
    "level cap",
    "level-up",
    "XP overflow",
    "skill decay",
    "significance weighting",
    "last_used",
    "grant_xp",
    "decay_all"
  ],
  "categories": [
    "testing",
    "skills system",
    "gamification",
    "soul evolution",
    "test"
  ],
  "source_docs": [
    "0903ad3342ab7cc6"
  ],
  "backlinks": null,
  "word_count": 492,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Skills give a soul a quantified record of what it has practiced. Rather than a flat count of interactions, the XP model creates non-linear progression where early levels come quickly and later levels require sustained effort. This test file exists to pin the XP scaling math, enforce the level cap, and verify that decay (XP erosion for unused skills) never produces invalid states.

## Skill Construction

A `Skill` starts at level 1 with 0 XP and needs 100 XP to reach level 2:

```python
skill = Skill(id="coding", name="Coding")
assert skill.level == 1
assert skill.xp == 0
assert skill.xp_to_next == 100
```

The `config` dict allows arbitrary skill-specific metadata (e.g., `{"style": "watercolor"}` for an art skill), enabling domain-specific extensions without modifying the model.

## XP and Leveling

The XP-to-next threshold scales at 1.5× per level:
- Level 1→2: 100 XP needed, next threshold = 150
- Level 2→3: 150 XP needed, next threshold = 225

`add_xp(amount)` returns `True` if a level-up occurred. Overflow XP carries forward:

```python
skill.add_xp(130)  # needed 100, got 130
assert skill.level == 2
assert skill.xp == 30       # 30 carried
assert skill.xp_to_next == 150
```

This prevents the "level tax" problem where XP earned past a threshold is lost.

## Level Cap and Last Used

At level 10, `add_xp()` returns `False` and does not increment the level, but XP continues to accumulate. This allows a level-10 skill to still record activity without the implementation needing a special "overflow" state. The `last_used` timestamp is updated on every `add_xp()` call, enabling decay to measure time-since-use accurately.

## SkillRegistry

`SkillRegistry` is the collection that holds all of a soul's skills:

- `add(skill)`: Adds a skill; adding a duplicate (same `id`) is silently ignored to prevent double-registration
- `get(id)`: Returns `None` for missing skills (not a `KeyError`)
- `grant_xp(id, amount)`: XP grants on missing skills are also silently ignored, preventing crashes when an activity references a skill the soul has not yet acquired

## Skill Decay

The `decay()` method reduces a skill's XP over time for unused skills:

- XP floors at 0 (never goes negative)
- Decay never reduces `level` — the soul keeps its earned rank even if it stops practicing
- `SkillRegistry.decay_all()` returns the count of skills that decayed, enabling callers to decide whether to notify the user

Significance-weighted XP tests verify that high-significance interactions grant more XP than low-significance ones, connecting the skills system to the broader significance scoring pipeline.

## Data Flow

```
Soul.observe(interaction)
  └─ significance scoring
  └─ SkillRegistry.grant_xp(skill_id, base_xp * significance)
       └─ Skill.add_xp(amount)
            └─ updates xp, level, xp_to_next, last_used
```

## Known Gaps

No TODO or FIXME markers. The test for `add_xp` at level 10 only checks that level stays at 10 and XP accumulates — there is no test for what happens when a level-10 skill's accumulated XP is used for a prestige reset or similar mechanic. The significance-weighting tests use hardcoded thresholds (`test_significance_weighted_xp_high`, `test_significance_weighted_xp_low`) that would silently break if the weighting formula changes.