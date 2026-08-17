# Engine-level module — opinionated XP/leveling system. Not part of the core protocol.
# skills.py — Skills/XP progression system for souls
# Created: 2026-03-06 — Implements Skill and SkillRegistry with XP/leveling
# Updated: 2026-03-22 — Added grant_xp_from_learning().
# Updated: 2026-03-29 — Added Skill.decay() and SkillRegistry.decay_all() for
#   significance-weighted XP and time-based XP decay (F3: Skills XP).
# Updated: 2026-06-16 (feat/soul-skills-procedural) — Added
#   grant_xp_for_procedure_use(): grants XP to the skill tracking a learned
#   procedure each time that procedure is used, auto-creating the skill on
#   first use. Returns True when the grant crosses a level boundary (the
#   graduation signal PocketPaw's skills loop uses to materialize a SKILL.md).
# Updated: 2026-08-03 (#292) — Added SkillSource enum and Skill.source field
#   so entity-derived skills (auto-created from extracted names during observe())
#   can be excluded from public_profile() and A2A agent cards.  Added
#   SkillRegistry.public_skills() to centralize the filter.
# Updated: 2026-08-08 (#292 review) — source defaults to None (fail-closed for
#   legacy souls on disk).  add() upgrades source on id collision so a later
#   explicit MANUAL registration overrides an earlier ENTITY squatter.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from soul_protocol.spec.learning import LearningEvent


class SkillSource(StrEnum):
    """How a skill was created — controls public-surface visibility.

    ``ENTITY`` skills are auto-created from extracted entity names during
    ``observe()`` and may contain private person/organisation names.  They
    are excluded from ``public_profile()`` and A2A agent cards (#292).
    """

    MANUAL = "manual"  # explicitly registered by user/developer
    ENTITY = "entity"  # auto-created from extracted entity names
    PROCEDURE = "procedure"  # auto-created by grant_xp_for_procedure_use
    LEARNING = "learning"  # auto-created by grant_xp_from_learning


class Skill(BaseModel):
    """A learned ability with XP progression."""

    id: str
    name: str
    level: int = Field(default=1, ge=1, le=10)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = 100  # XP needed for next level
    config: dict = Field(default_factory=dict)
    last_used: datetime = Field(default_factory=datetime.now)
    source: SkillSource | None = None

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
        """Add a skill, or upgrade source on id collision.

        If a skill with the same id already exists and the new skill has an
        explicitly higher-trust source (e.g. MANUAL over ENTITY), upgrade
        the existing skill's source.  This prevents an ENTITY skill from
        permanently squatting an id and silently hiding a later legitimate
        registration (#292 review).
        """
        existing = self.get(skill.id)
        if existing is None:
            self.skills.append(skill)
        elif skill.source == SkillSource.MANUAL and existing.source != SkillSource.MANUAL:
            existing.source = SkillSource.MANUAL
            existing.name = skill.name  # adopt the explicit name

    def public_skills(self) -> list[Skill]:
        """Return skills safe for public exposure.

        Only skills with an **explicit, trusted source** are included:
        ``MANUAL`` and ``PROCEDURE``.  Skills with ``source=None`` (legacy
        data without provenance) or ``ENTITY`` (auto-created from extracted
        names) are excluded.  This is fail-closed: unknown provenance is
        treated as potentially private (#292).
        """
        _PUBLIC_SOURCES = {SkillSource.MANUAL, SkillSource.PROCEDURE}
        return [s for s in self.skills if s.source in _PUBLIC_SOURCES]

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

    def grant_xp_for_procedure_use(self, skill_id: str, amount: int = 10) -> bool:
        """Grant XP to the skill that tracks a learned procedure's usage.

        Called by the self-improving skills loop whenever an agent-learned
        procedure is used. Auto-creates the skill (named after ``skill_id``)
        on first use so callers never have to pre-register it.

        Args:
            skill_id: Stable id tying a procedure to its progression skill —
                e.g. ``"proc:<memory_id>"``.
            amount: XP to grant per use (default 10).

        Returns:
            True if the grant crossed a level boundary — the graduation signal
            the loop uses to materialize a SKILL.md.
        """
        skill = self.get(skill_id)
        if not skill:
            skill = Skill(id=skill_id, name=skill_id, source=SkillSource.PROCEDURE)
            self.add(skill)
        return skill.add_xp(amount)

    def grant_xp_from_learning(self, event: LearningEvent) -> bool:
        """Grant XP to a skill based on a LearningEvent."""
        skill_id = event.skill_id
        if not skill_id:
            skill_id = event.domain.lower().replace(" ", "_")
        skill = self.get(skill_id)
        if not skill:
            skill = Skill(id=skill_id, name=event.domain, source=SkillSource.LEARNING)
            self.add(skill)
        score = event.evaluation_score if event.evaluation_score is not None else 0.5
        xp_amount = int(20 * (0.5 + score) * event.confidence)
        xp_amount = max(1, xp_amount)
        return skill.add_xp(xp_amount)
