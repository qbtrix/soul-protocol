# Engine-level module — opinionated XP/leveling system. Not part of the core protocol.
# skills.py — Skills/XP progression system for souls
# Created: 2026-03-06 — Implements Skill and SkillRegistry with XP/leveling

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
