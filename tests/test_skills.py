# test_skills.py — Tests for the Skills/XP progression system
# Created: 2026-03-06 — Skill creation, XP, leveling, level cap, registry

from __future__ import annotations

import pytest

from soul_protocol.skills import Skill, SkillRegistry


class TestSkillCreation:
    """Tests for Skill default construction."""

    def test_default_skill(self):
        skill = Skill(id="coding", name="Coding")
        assert skill.id == "coding"
        assert skill.name == "Coding"
        assert skill.level == 1
        assert skill.xp == 0
        assert skill.xp_to_next == 100

    def test_skill_with_config(self):
        skill = Skill(id="art", name="Art", config={"style": "watercolor"})
        assert skill.config == {"style": "watercolor"}


class TestSkillXP:
    """Tests for Skill.add_xp()."""

    def test_add_xp_no_levelup(self):
        skill = Skill(id="coding", name="Coding")
        leveled = skill.add_xp(50)
        assert leveled is False
        assert skill.xp == 50
        assert skill.level == 1

    def test_add_xp_triggers_levelup(self):
        skill = Skill(id="coding", name="Coding")
        leveled = skill.add_xp(100)
        assert leveled is True
        assert skill.level == 2
        assert skill.xp == 0
        assert skill.xp_to_next == 150  # 100 * 1.5

    def test_add_xp_overflow_carries(self):
        skill = Skill(id="coding", name="Coding")
        leveled = skill.add_xp(130)
        assert leveled is True
        assert skill.level == 2
        assert skill.xp == 30
        assert skill.xp_to_next == 150

    def test_xp_scaling_across_levels(self):
        skill = Skill(id="coding", name="Coding")
        # Level 1 -> 2: need 100 XP, next = 150
        skill.add_xp(100)
        assert skill.level == 2
        assert skill.xp_to_next == 150

        # Level 2 -> 3: need 150 XP, next = 225
        skill.add_xp(150)
        assert skill.level == 3
        assert skill.xp_to_next == 225

    def test_level_cap_at_10(self):
        skill = Skill(id="coding", name="Coding", level=10, xp=0)
        leveled = skill.add_xp(999)
        assert leveled is False
        assert skill.level == 10
        assert skill.xp == 999  # XP still accumulates

    def test_add_xp_updates_last_used(self):
        from datetime import datetime
        skill = Skill(id="coding", name="Coding")
        before = skill.last_used
        skill.add_xp(10)
        # last_used should be updated (at least not before the original)
        assert skill.last_used >= before


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_empty_registry(self):
        registry = SkillRegistry()
        assert len(registry.skills) == 0

    def test_add_skill(self):
        registry = SkillRegistry()
        skill = Skill(id="coding", name="Coding")
        registry.add(skill)
        assert len(registry.skills) == 1
        assert registry.get("coding") is not None

    def test_add_duplicate_ignored(self):
        registry = SkillRegistry()
        registry.add(Skill(id="coding", name="Coding"))
        registry.add(Skill(id="coding", name="Coding v2"))
        assert len(registry.skills) == 1
        assert registry.get("coding").name == "Coding"

    def test_get_missing_returns_none(self):
        registry = SkillRegistry()
        assert registry.get("nonexistent") is None

    def test_grant_xp_existing_skill(self):
        registry = SkillRegistry()
        registry.add(Skill(id="coding", name="Coding"))
        leveled = registry.grant_xp("coding", 50)
        assert leveled is False
        assert registry.get("coding").xp == 50

    def test_grant_xp_levelup(self):
        registry = SkillRegistry()
        registry.add(Skill(id="coding", name="Coding"))
        leveled = registry.grant_xp("coding", 100)
        assert leveled is True
        assert registry.get("coding").level == 2

    def test_grant_xp_missing_skill(self):
        registry = SkillRegistry()
        result = registry.grant_xp("nonexistent", 50)
        assert result is False

    def test_multiple_skills(self):
        registry = SkillRegistry()
        registry.add(Skill(id="coding", name="Coding"))
        registry.add(Skill(id="art", name="Art"))
        registry.add(Skill(id="music", name="Music"))
        assert len(registry.skills) == 3
        assert registry.get("art").name == "Art"
