"""Tests for the bundled role templates + SoulFactory.load_template (Move 6 PR-A).

Created: 2026-04-13 — Locks the bundled archetype contracts (Arrow/Flash/
Cyborg/Analyst), the YAML and JSON loaders, the missing-file behaviour,
and end-to-end instantiation against a real Soul. Companion tests for
SoulFactory.from_template / batch_spawn live in test_soul_templates.py
and stay untouched.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from soul_protocol.runtime.templates import SoulFactory
from soul_protocol.spec.template import SoulTemplate
from soul_protocol.templates import (
    BUNDLED_TEMPLATES,
    list_bundled,
    template_path,
)

# ---------------------------------------------------------------------------
# Bundled inventory
# ---------------------------------------------------------------------------


class TestBundledInventory:
    def test_all_expected_templates_are_bundled(self) -> None:
        on_disk = set(list_bundled())
        for expected in BUNDLED_TEMPLATES:
            assert expected in on_disk, f"Missing bundled template: {expected}"

    @pytest.mark.parametrize("name", BUNDLED_TEMPLATES)
    def test_bundled_template_loads_and_validates(self, name: str) -> None:
        tmpl = SoulFactory.load_bundled(name)
        assert isinstance(tmpl, SoulTemplate)
        assert tmpl.name
        assert tmpl.archetype
        for trait, value in tmpl.personality.items():
            assert 0.0 <= value <= 1.0, f"{name}.{trait} out of range: {value}"

    def test_arrow_carries_recommended_default_scope(self) -> None:
        arrow = SoulFactory.load_bundled("arrow")
        scopes = arrow.metadata.get("default_scope", [])
        assert "org:sales:*" in scopes

    def test_cyborg_metadata_includes_recommended_tools(self) -> None:
        cyborg = SoulFactory.load_bundled("cyborg")
        tools = cyborg.metadata.get("recommended_tools", [])
        assert "instinct_propose" in tools

    def test_each_bundled_template_has_at_least_one_skill(self) -> None:
        for name in BUNDLED_TEMPLATES:
            tmpl = SoulFactory.load_bundled(name)
            assert tmpl.skills, f"{name} ships with no skills"


# ---------------------------------------------------------------------------
# Generic loader
# ---------------------------------------------------------------------------


class TestLoadTemplate:
    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        path = tmp_path / "custom.yaml"
        path.write_text(
            textwrap.dedent(
                """
                name: Helper
                archetype: The Test Companion
                personality:
                  openness: 0.7
                  conscientiousness: 0.6
                core_memories:
                  - "I am a test."
                skills:
                  - test
                """,
            ).strip(),
            encoding="utf-8",
        )
        tmpl = SoulFactory.load_template(path)
        assert tmpl.name == "Helper"
        assert tmpl.personality["openness"] == 0.7
        assert tmpl.skills == ["test"]

    def test_loads_json_file(self, tmp_path: Path) -> None:
        path = tmp_path / "custom.json"
        path.write_text(
            json.dumps(
                {
                    "name": "Helper",
                    "archetype": "The JSON Companion",
                    "personality": {"openness": 0.5},
                    "core_memories": [],
                    "skills": [],
                }
            ),
            encoding="utf-8",
        )
        tmpl = SoulFactory.load_template(path)
        assert tmpl.name == "Helper"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            SoulFactory.load_template(tmp_path / "nope.yaml")


# ---------------------------------------------------------------------------
# End-to-end — instantiate a real Soul from a bundled template
# ---------------------------------------------------------------------------


class TestInstantiation:
    @pytest.mark.asyncio
    async def test_from_template_creates_soul_with_archetype(self) -> None:
        arrow = SoulFactory.load_bundled("arrow")
        soul = await SoulFactory.from_template(arrow)
        assert soul.name == "Arrow"

    @pytest.mark.asyncio
    async def test_from_template_seeds_core_memories(self) -> None:
        flash = SoulFactory.load_bundled("flash")
        soul = await SoulFactory.from_template(flash)
        assert soul.memory_count >= len(flash.core_memories)

    @pytest.mark.asyncio
    async def test_from_template_overrides_name(self) -> None:
        analyst = SoulFactory.load_bundled("analyst")
        soul = await SoulFactory.from_template(analyst, name="Custom Analyst")
        assert soul.name == "Custom Analyst"

    @pytest.mark.asyncio
    async def test_from_template_propagates_default_scope(self) -> None:
        """Arrow declares default_scope: [org:sales:*]. Seeded core memories
        should carry that scope so Move 5 match_scope filtering works on a
        freshly-instantiated soul (no extra wiring needed)."""
        arrow = SoulFactory.load_bundled("arrow")
        assert arrow.metadata.get("default_scope") == ["org:sales:*"]

        soul = await SoulFactory.from_template(arrow)
        # Every seeded memory in the underlying store should carry the
        # template's default_scope tag, ready for match_scope filtering at
        # recall time.
        from soul_protocol.spec.scope import match_scope

        entries = list(soul._memory._semantic._facts.values())
        assert entries, "no core memories seeded into the semantic store"
        for entry in entries:
            assert entry.scope == ["org:sales:*"], f"missing scope on {entry.id}"

        # match_scope semantics: a caller granted a parent/glob scope can
        # see entity-scoped memories. A caller granted an unrelated scope
        # cannot.
        sales_admin = ["org:sales:*"]
        hr_admin = ["org:hr:*"]
        assert all(match_scope(e.scope, sales_admin) for e in entries)
        assert not any(match_scope(e.scope, hr_admin) for e in entries)

    @pytest.mark.asyncio
    async def test_arrow_core_memories_visible_to_concrete_sales_caller(self) -> None:
        """v0.3.1 follow-up: a sales agent installed from Arrow with a
        concrete caller scope (`org:sales:leads`) must still see the
        template's core memories tagged with the glob `org:sales:*`.
        Before the match_scope containment fix this returned no results."""
        arrow = SoulFactory.load_bundled("arrow")
        soul = await SoulFactory.from_template(arrow)

        from soul_protocol.spec.scope import match_scope

        entries = list(soul._memory._semantic._facts.values())
        assert entries
        concrete_caller = ["org:sales:leads"]
        assert all(match_scope(e.scope, concrete_caller) for e in entries)


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


class TestTemplateHelpers:
    def test_template_path_returns_yaml_extension(self) -> None:
        path = template_path("arrow")
        assert path.suffix == ".yaml"
        assert path.name == "arrow.yaml"

    def test_list_bundled_includes_canonical_set(self) -> None:
        names = list_bundled()
        for expected in ("arrow", "flash", "cyborg", "analyst"):
            assert expected in names
