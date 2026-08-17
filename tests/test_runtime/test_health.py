from __future__ import annotations

from soul_protocol.runtime.health import CleanupAction, audit_health, execute_cleanup, plan_cleanup
from soul_protocol.runtime.skills import Skill
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType


async def test_audit_health_reports_structured_issue_fields():
    soul = await Soul.birth("HealthIssues", archetype="Test", values=["clarity"])
    soul.skills.skills.append(
        Skill.model_construct(id="orphan-cleanup", name="orphan-cleanup", level=1, xp=-1)
    )

    report = await audit_health(soul)

    assert report.skill_issues == ["Skill orphan-cleanup has negative XP (-1)"]
    assert report.bond_issues == []
    assert report.issues == report.skill_issues
    assert report.healthy is False

    # Structured fields must appear in JSON payload for MCP clients
    d = report.to_dict()
    assert d["bond_issues"] == []
    assert d["skill_issues"] == ["Skill orphan-cleanup has negative XP (-1)"]
    assert "issues" in d  # flattened list still present for backward compat


async def test_audit_health_counts_duplicates_stale_evals_and_orphans():
    soul = await Soul.birth("HealthCounts", archetype="Test", values=["clarity"])
    await soul.remember("User likes Python programming", importance=6)
    await soul.remember("User likes Python programming", importance=6)
    await soul.remember("Scored empathy eval at 0.8", type=MemoryType.PROCEDURAL, importance=4)

    for index in range(11):
        soul._memory._graph.add_entity(f"OrphanNode{index}", "concept")

    report = await audit_health(soul)

    assert report.duplicate_count == 1
    assert report.stale_eval_count == 1
    assert report.orphan_node_count == 11
    assert "1 duplicate memories (>80% overlap)" in report.issues
    assert "11 orphan graph nodes" in report.issues


async def test_plan_cleanup_honors_each_mode_flag():
    soul = await Soul.birth("CleanupPlan", archetype="Test", values=["clarity"])
    await soul.remember("User likes Python programming", importance=6)
    await soul.remember("User likes Python programming", importance=6)
    await soul.remember("Scored safety eval at 0.7", type=MemoryType.PROCEDURAL, importance=4)
    await soul.remember("Tiny note", importance=1)
    soul._memory._graph.add_entity("DetachedGraphNode", "concept")

    actions = await plan_cleanup(
        soul,
        dedup=True,
        stale_evals=True,
        orphan_nodes=False,
        low_importance=2,
    )

    assert {a.action_type for a in actions} == {"dedup", "stale_evals", "low_importance"}

    actions = await plan_cleanup(
        soul,
        dedup=False,
        stale_evals=False,
        orphan_nodes=True,
        low_importance=0,
    )

    assert {a.action_type for a in actions} == {"orphan_nodes"}


async def test_execute_cleanup_counts_only_actual_removals():
    soul = await Soul.birth("CleanupExecute", archetype="Test", values=["clarity"])
    memory_id = await soul.remember("Disposable memory", importance=1)
    soul._memory._graph.add_entity("DisposableNode", "concept")

    removed = await execute_cleanup(
        soul,
        [
            CleanupAction("low_importance", "semantic", [memory_id]),
            CleanupAction("dedup", "semantic", [memory_id]),
            CleanupAction("orphan_nodes", "graph", ["DisposableNode", "DisposableNode"]),
        ],
    )

    assert removed == 2
    assert all(entry.id != memory_id for entry in soul._memory._semantic.facts())
    assert "DisposableNode" not in soul._memory._graph.entities()
