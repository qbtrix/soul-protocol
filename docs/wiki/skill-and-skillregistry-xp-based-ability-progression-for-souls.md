---
{
  "title": "Skill and SkillRegistry: XP-Based Ability Progression for Souls",
  "summary": "Implements a leveled skill system where souls gain experience points (XP) through interactions, level up abilities (1-10) with exponential scaling thresholds, and lose XP through time-based decay when skills go unused. SkillRegistry manages the collection and bridges the learning event pipeline.",
  "concepts": [
    "skills",
    "XP progression",
    "leveling system",
    "SkillRegistry",
    "decay",
    "LearningEvent",
    "experience points",
    "Pydantic BaseModel",
    "companion evolution",
    "soul abilities"
  ],
  "categories": [
    "skills",
    "evolution",
    "gamification",
    "soul-lifecycle"
  ],
  "source_docs": [
    "0533940a645e8b80"
  ],
  "backlinks": null,
  "word_count": 461,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why Skills?

Soul Protocol's vision is that companions evolve through experience. A soul that has handled hundreds of coding questions should become measurably better at it — not just through better memories, but through a formal competency model. Skills provide that model: a quantified representation of the soul's accumulated expertise per domain.

Skills are explicitly labeled as engine-level and opinionated (per the module header), meaning they are not part of the core portability spec — they are a feature that deployments can opt into.

## Skill Model

```python
class Skill(BaseModel):
    id: str
    name: str
    level: int = Field(default=1, ge=1, le=10)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = 100
    last_used: datetime
```

Levels range 1–10 with `ge=1, le=10` constraints enforced by Pydantic. XP requirements scale exponentially:

```python
def add_xp(self, amount: int) -> bool:
    self.xp += amount
    self.last_used = datetime.now()
    if self.xp >= self.xp_to_next and self.level < 10:
        self.xp -= self.xp_to_next
        self.level += 1
        self.xp_to_next = int(self.xp_to_next * 1.5)  # Exponential scaling
        return True
    return False
```

The 1.5x multiplier means level 1→2 costs 100 XP, level 9→10 costs ~3,800 XP — reaching mastery requires sustained use, not a burst.

## XP Decay

`Skill.decay()` subtracts one XP per day of inactivity, flooring at 0 but never reducing level:

```python
def decay(self, days_inactive: int) -> None:
    self.xp = max(0, self.xp - days_inactive)
```

The "never reduce level" rule is critical for user experience: a companion that loses its level after a vacation feels broken. Decay reduces the XP buffer within the current level, creating a "use-it-or-slowly-lose-progress" dynamic without catastrophic resets.

`SkillRegistry.decay_all()` is called by `Soul.observe()` before processing each interaction, keeping decay current without requiring a background job.

## Learning Event Bridge

`grant_xp_from_learning()` connects the formal `LearningEvent` spec to the XP system:

```python
def grant_xp_from_learning(self, event: LearningEvent) -> bool:
    amount = max(5, min(30, int(event.significance * 30)))
    return self.grant_xp(event.skill_id, amount)
```

`significance` (0.0–1.0) from the learning event maps to 5–30 XP, giving minor interactions a small reward and breakthrough moments a large one. The `max(5, ...)` floor ensures even low-significance events register — no interaction is worthless.

## Idempotency Guard on Add

`SkillRegistry.add()` checks for an existing skill with the same ID before inserting:

```python
def add(self, skill: Skill) -> None:
    if not self.get(skill.id):
        self.skills.append(skill)
```

Without this guard, re-awakening a soul and re-seeding its skills (e.g., from `SoulFactory`) would create duplicate entries, causing `grant_xp()` to only update the first occurrence while the second silently diverges.

## Known Gaps

- `decay_all()` uses `datetime.now()` which is the local system clock without timezone awareness. In containerized or cloud deployments that change timezone, decay calculations can drift.
- Skill IDs are arbitrary strings — there is no registry of canonical skill names. Two deployments could use `"coding"` and `"code"` for the same ability, making cross-soul comparison meaningless.
