# Engine-level module — opinionated XP/leveling system. Not part of the core protocol.
# skills.py — Skills/XP progression system for souls
# Created: 2026-03-06 — Implements Skill and SkillRegistry with XP/leveling
# Updated: 2026-03-22 — Added grant_xp_from_learning().
# Updated: 2026-03-29 — Added Skill.decay() and SkillRegistry.decay_all() for
#   significance-weighted XP and time-based XP decay (F3: Skills XP).

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from soul_protocol.spec.learning import LearningEvent


class Skill(BaseModel):
    """A learned ability with XP progression."""

    id: str
    name: str
    level: int = Field(default=1, ge=1, le=10)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = 100  # XP needed for next level
    config: dict = Field(default_factory=dict)
    last_used: datetime = Field(default_factory=datetime.now)

    def add_xp(self, amount: int) -> bool:
        """Add XP. Returns True if leveled up."""
        self.xp += amount
        self.last_used = datetime.now()
        if self.xp >= self.xp_to_next and self.level < 10:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = int(self.xp_to_next * 1.5)  # Exponential scaling
            return True
        return False

    def decay(self, days_inactive: int) -> None:
        """Reduce XP by days_inactive (1 XP per day). Floors at 0. Never reduces level."""
        self.xp = max(0, self.xp - days_inactive)


class SkillRegistry(BaseModel):
    """Collection of skills for a soul."""

    skills: list[Skill] = Field(default_factory=list)

    def get(self, skill_id: str) -> Skill | None:
        return next((s for s in self.skills if s.id == skill_id), None)

    def add(self, skill: Skill) -> None:
        if not self.get(skill.id):
            self.skills.append(skill)

    def grant_xp(self, skill_id: str, amount: int) -> bool:
        skill = self.get(skill_id)
        if skill:
            return skill.add_xp(amount)
        return False

    def decay_all(self, now: datetime | None = None) -> int:
        """Apply time-based XP decay to all skills.

        For each skill, computes days since last_used and calls skill.decay(days).
        Returns count of skills that had XP reduced.
        """
        if now is None:
            now = datetime.now()
        decayed = 0
        for skill in self.skills:
            days = (now - skill.last_used).days
            if days > 0:
                before = skill.xp
                skill.decay(days)
                if skill.xp < before:
                    decayed += 1
        return decayed

    def grant_xp_from_learning(self, event: LearningEvent) -> bool:
        """Grant XP to a skill based on a LearningEvent."""
        skill_id = event.skill_id
        if not skill_id:
            skill_id = event.domain.lower().replace(" ", "_")
        skill = self.get(skill_id)
        if not skill:
            skill = Skill(id=skill_id, name=event.domain)
            self.add(skill)
        score = event.evaluation_score if event.evaluation_score is not None else 0.5
        xp_amount = int(20 * (0.5 + score) * event.confidence)
        xp_amount = max(1, xp_amount)
        return skill.add_xp(xp_amount)
