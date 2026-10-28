# test_agent_provenance.py — Agent-created procedural provenance + curator.
# Created: 2026-06-16 (feat/soul-skills-procedural) — covers the substrate for
#   PocketPaw's self-improving skills loop: a MemoryProvenance tag distinguishing
#   agent-authored procedures from human-authored ones, threaded through
#   Soul.remember / Soul.note, plus a curator that consolidates and archives
#   AGENT-CREATED procedures only and never hard-deletes.

from __future__ import annotations

import pytest

from soul_protocol import Soul
from soul_protocol.runtime.skills import Skill, SkillRegistry
from soul_protocol.runtime.types import MemoryProvenance, MemoryType


@pytest.mark.asyncio
class TestProvenanceTagging:
    async def test_remember_defaults_to_human_provenance(self):
        soul = await Soul.birth("TestSoul")
        mid = await soul.remember("Deploy by running make ship", type=MemoryType.PROCEDURAL)
        entry = await soul._memory._procedural.get(mid)
        assert entry.provenance == MemoryProvenance.HUMAN

    async def test_remember_can_tag_agent_provenance(self):
        soul = await Soul.birth("TestSoul")
        mid = await soul.remember(
            "To regenerate C4, run make c4-pp from /docs",
            type=MemoryType.PROCEDURAL,
            provenance=MemoryProvenance.AGENT,
        )
        entry = await soul._memory._procedural.get(mid)
        assert entry.provenance == MemoryProvenance.AGENT

    async def test_note_threads_agent_provenance(self):
        soul = await Soul.birth("TestSoul")
        result = await soul.note(
            "When tests hang, check for an unawaited asyncio task",
            type=MemoryType.PROCEDURAL,
            provenance=MemoryProvenance.AGENT,
        )
        assert result["action"] == "CREATE"
        entry = await soul._memory._procedural.get(result["id"])
        assert entry.provenance == MemoryProvenance.AGENT

    async def test_agent_and_human_entries_are_distinguishable(self):
        soul = await Soul.birth("TestSoul")
        await soul.remember("Human wrote this one", type=MemoryType.PROCEDURAL)
        await soul.remember(
            "Agent learned this one",
            type=MemoryType.PROCEDURAL,
            provenance=MemoryProvenance.AGENT,
        )
        agent_entries = [
            e for e in soul._memory._procedural.entries() if e.provenance == MemoryProvenance.AGENT
        ]
        human_entries = [
            e for e in soul._memory._procedural.entries() if e.provenance == MemoryProvenance.HUMAN
        ]
        assert len(agent_entries) == 1
        assert len(human_entries) == 1
        assert agent_entries[0].content == "Agent learned this one"


@pytest.mark.asyncio
class TestCurator:
    async def test_consolidate_supersedes_overlapping_agent_procedures(self):
        soul = await Soul.birth("TestSoul")
        # Two near-duplicate agent procedures (dedup is bypassed by remember()).
        await soul.remember(
            "To run the e2e suite use uv run pytest tests e2e directory",
            type=MemoryType.PROCEDURAL,
            provenance=MemoryProvenance.AGENT,
        )
        await soul.remember(
            "To run the e2e suite use uv run pytest tests e2e directory always",
            type=MemoryType.PROCEDURAL,
            provenance=MemoryProvenance.AGENT,
        )
        report = await soul.curate_agent_procedures()
        # One of the overlapping pair is superseded (never hard-deleted).
        assert report["consolidated"] >= 1
        superseded = [e for e in soul._memory._procedural.entries() if e.superseded]
        assert len(superseded) >= 1
        # The superseded entry still exists in the store (no hard delete).
        assert all(s.id for s in superseded)

    async def test_curator_never_touches_human_procedures(self):
        soul = await Soul.birth("TestSoul")
        # Two overlapping HUMAN procedures must be left untouched.
        h1 = await soul.remember(
            "To run the e2e suite use uv run pytest tests e2e directory",
            type=MemoryType.PROCEDURAL,
        )
        h2 = await soul.remember(
            "To run the e2e suite use uv run pytest tests e2e directory always",
            type=MemoryType.PROCEDURAL,
        )
        await soul.curate_agent_procedures()
        e1 = await soul._memory._procedural.get(h1)
        e2 = await soul._memory._procedural.get(h2)
        assert not e1.superseded
        assert not e2.superseded

    async def test_curator_never_hard_deletes(self):
        soul = await Soul.birth("TestSoul")
        ids = []
        for i in range(3):
            ids.append(
                await soul.remember(
                    f"Agent procedure number {i} for running the deploy pipeline cleanly",
                    type=MemoryType.PROCEDURAL,
                    provenance=MemoryProvenance.AGENT,
                )
            )
        count_before = len(soul._memory._procedural.entries())
        await soul.curate_agent_procedures()
        count_after = len(soul._memory._procedural.entries())
        # Curator marks, never removes — store size is unchanged.
        assert count_after == count_before


class TestGraduationXP:
    def test_grant_xp_for_procedure_use_crosses_threshold(self):
        registry = SkillRegistry()
        registry.add(Skill(id="proc:deploy", name="deploy", xp=95, xp_to_next=100))
        graduated = registry.grant_xp_for_procedure_use("proc:deploy", amount=10)
        assert graduated is True
        skill = registry.get("proc:deploy")
        assert skill.level == 2

    def test_grant_xp_creates_skill_when_absent(self):
        registry = SkillRegistry()
        registry.grant_xp_for_procedure_use("proc:newproc", amount=5)
        skill = registry.get("proc:newproc")
        assert skill is not None
        assert skill.xp == 5
