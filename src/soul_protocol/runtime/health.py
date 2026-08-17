# runtime/health.py — Shared health-audit and cleanup logic (#288).
# Created: 2026-07-21
#
# Single source of truth for soul health audits and cleanups.
# Both the CLI (`health_cmd`, `cleanup_cmd`) and the MCP server
# (`soul_health`, `soul_cleanup`) delegate to these functions
# so logic never drifts between entry points.
# Updated: #288 review — keep bond/skill issues structured, preserve MCP
#   cleanup response compatibility, and count only actual removals.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes — callers format these however they want (JSON, Rich, etc.)
# ---------------------------------------------------------------------------


@dataclass
class HealthReport:
    """Result of a soul health audit."""

    soul_name: str

    # Memory tiers
    episodic_count: int = 0
    semantic_count: int = 0
    procedural_count: int = 0
    social_count: int = 0

    # Knowledge & skills
    graph_node_count: int = 0
    skill_count: int = 0
    eval_history_count: int = 0

    # Bond
    bond_strength: float = 0.0
    bond_interactions: int = 0

    # Detected issues
    duplicate_count: int = 0
    low_importance_count: int = 0
    stale_eval_count: int = 0
    orphan_node_count: int = 0
    bond_issues: list[str] = field(default_factory=list)
    skill_issues: list[str] = field(default_factory=list)

    @property
    def total_memories(self) -> int:
        return self.episodic_count + self.semantic_count + self.procedural_count + self.social_count

    @property
    def healthy(self) -> bool:
        return len(self.issues) == 0

    @property
    def issues(self) -> list[str]:
        issues = [*self.bond_issues, *self.skill_issues]
        if self.duplicate_count > 0:
            issues.append(f"{self.duplicate_count} duplicate memories (>80% overlap)")
        if self.orphan_node_count > 10:
            issues.append(f"{self.orphan_node_count} orphan graph nodes")
        return issues

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for JSON output."""
        return {
            "soul": self.soul_name,
            "tiers": {
                "episodic": self.episodic_count,
                "semantic": self.semantic_count,
                "procedural": self.procedural_count,
                "social": self.social_count,
                "total": self.total_memories,
            },
            "graph_nodes": self.graph_node_count,
            "skills": self.skill_count,
            "eval_history": self.eval_history_count,
            "bond_strength": round(self.bond_strength, 2),
            "bond_interactions": self.bond_interactions,
            "duplicates": self.duplicate_count,
            "low_importance": self.low_importance_count,
            "stale_evals": self.stale_eval_count,
            "orphan_nodes": self.orphan_node_count,
            "bond_issues": self.bond_issues,
            "skill_issues": self.skill_issues,
            "issues": self.issues,
            "healthy": self.healthy,
        }


@dataclass
class CleanupAction:
    """A single cleanup action (dedup, stale_evals, orphan_nodes, etc.)."""

    action_type: str  # "dedup" | "stale_evals" | "orphan_nodes" | "low_importance"
    tier: str  # "episodic" | "semantic" | "procedural" | "graph"
    item_ids: set | list = field(default_factory=set)

    @property
    def count(self) -> int:
        return len(self.item_ids)


@dataclass
class CleanupResult:
    """Result of a soul cleanup operation."""

    soul_name: str
    status: str  # "dry_run" | "clean" | "cleaned"
    actions: list[CleanupAction] = field(default_factory=list)
    total_removed: int = 0
    backup_path: str | None = None

    @property
    def total_items(self) -> int:
        return sum(a.count for a in self.actions)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for JSON output."""
        return {
            "soul": self.soul_name,
            "status": self.status,
            "total_items": self.total_items,
            "removed": self.total_removed,
            "total_removed": self.total_removed,
            "backup": self.backup_path,
            "actions": [
                {
                    "action": a.action_type,
                    "tier": a.tier,
                    "count": a.count,
                }
                for a in self.actions
            ],
        }


# ---------------------------------------------------------------------------
# audit_health — replaces duplicated logic in MCP + CLI
# ---------------------------------------------------------------------------


async def audit_health(soul: Soul) -> HealthReport:
    """Run a health audit on a soul's memory, skills, bond, and graph.

    This is the single source of truth for health checks.  Both the CLI
    ``health`` command and the MCP ``soul_health`` tool call this.
    """
    from soul_protocol.runtime.memory.compression import MemoryCompressor

    mm = soul.memory

    episodic = list(mm.episodic_entries())
    semantic = list(mm.semantic_facts())
    procedural = list(mm.procedural_entries())
    social = list(mm.social_entries())
    graph_nodes = mm.graph_entities()
    skills = soul.skills.skills
    evals = soul.eval_history

    # Detect duplicates
    compressor = MemoryCompressor()
    all_mems = episodic + semantic + procedural + social
    deduped = compressor.deduplicate(all_mems, similarity_threshold=0.8)
    dup_count = len(all_mems) - len(deduped)

    # Low-importance
    low_imp = [m for m in all_mems if m.importance <= 2]

    # Stale eval procedurals
    stale_proc = [p for p in procedural if p.content.startswith("Scored ")]

    # Orphan graph nodes (nodes not referenced in any memory)
    all_content = " ".join(m.content for m in all_mems)
    orphan_nodes = [n for n in graph_nodes if n.lower() not in all_content.lower() and len(n) > 2]

    # Bond sanity
    bond = soul.bond
    bond_issues: list[str] = []
    if bond.bond_strength > 100:
        bond_issues.append(f"Bond strength {bond.bond_strength:.0f} exceeds 100")
    if bond.bond_strength < 0:
        bond_issues.append(f"Bond strength {bond.bond_strength:.0f} is negative")

    # Skill sanity
    skill_issues: list[str] = []
    for sk in skills:
        if sk.xp < 0:
            skill_issues.append(f"Skill {sk.id} has negative XP ({sk.xp})")
        if sk.level < 1 or sk.level > 10:
            skill_issues.append(f"Skill {sk.id} has invalid level ({sk.level})")

    return HealthReport(
        soul_name=soul.name,
        episodic_count=len(episodic),
        semantic_count=len(semantic),
        procedural_count=len(procedural),
        social_count=len(social),
        graph_node_count=len(graph_nodes),
        skill_count=len(skills),
        eval_history_count=len(evals),
        bond_strength=bond.bond_strength,
        bond_interactions=bond.interaction_count,
        duplicate_count=dup_count,
        low_importance_count=len(low_imp),
        stale_eval_count=len(stale_proc),
        orphan_node_count=len(orphan_nodes),
        bond_issues=bond_issues,
        skill_issues=skill_issues,
    )


# ---------------------------------------------------------------------------
# plan_cleanup / execute_cleanup — replaces duplicated logic in MCP + CLI
# ---------------------------------------------------------------------------


async def plan_cleanup(
    soul: Soul,
    *,
    dedup: bool = True,
    stale_evals: bool = True,
    orphan_nodes: bool = True,
    low_importance: int = 0,
) -> list[CleanupAction]:
    """Plan cleanup actions without executing them.

    Returns a list of ``CleanupAction`` describing what *would* be
    removed.  The CLI renders this as a preview; the MCP returns it as
    a ``dry_run`` JSON response.
    """
    from soul_protocol.runtime.memory.compression import MemoryCompressor

    mm = soul.memory
    actions: list[CleanupAction] = []

    # 1. Deduplicate
    if dedup:
        compressor = MemoryCompressor()
        for tier_name, fetch in [
            ("episodic", mm.episodic_entries),
            ("semantic", mm.semantic_facts),
            ("procedural", mm.procedural_entries),
            ("social", mm.social_entries),
        ]:
            entries = list(fetch())
            if not entries:
                continue
            deduped = compressor.deduplicate(entries, similarity_threshold=0.8)
            removed_ids = {m.id for m in entries} - {m.id for m in deduped}
            if removed_ids:
                actions.append(CleanupAction("dedup", tier_name, removed_ids))

    # 2. Stale evaluation procedurals
    if stale_evals:
        procedural = list(mm.procedural_entries())
        stale = [p for p in procedural if p.content.startswith("Scored ") and p.importance <= 5]
        if stale:
            actions.append(CleanupAction("stale_evals", "procedural", {p.id for p in stale}))

    # 3. Orphan graph nodes
    if orphan_nodes:
        all_mems = (
            list(mm.episodic_entries())
            + list(mm.semantic_facts())
            + list(mm.procedural_entries())
            + list(mm.social_entries())
        )
        all_content = " ".join(m.content for m in all_mems).lower()
        nodes = mm.graph_entities()
        orphans = [n for n in nodes if n.lower() not in all_content and len(n) > 2]
        if orphans:
            actions.append(CleanupAction("orphan_nodes", "graph", orphans))

    # 4. Low importance
    if low_importance > 0:
        for tier_name, fetch in [
            ("episodic", mm.episodic_entries),
            ("semantic", mm.semantic_facts),
        ]:
            entries = list(fetch())
            low = [m for m in entries if m.importance <= low_importance]
            if low:
                actions.append(CleanupAction("low_importance", tier_name, {m.id for m in low}))

    return actions


async def execute_cleanup(soul: Soul, actions: list[CleanupAction]) -> int:
    """Execute planned cleanup actions.  Returns the count of items removed.

    The caller is responsible for saving the soul afterwards.
    """
    mm = soul.memory
    removed = 0

    for action in actions:
        if action.action_type == "orphan_nodes":
            existing_nodes = set(mm.graph_entities())
            for node in action.item_ids:
                if node in existing_nodes:
                    mm.graph_remove_entity(node)
                    existing_nodes.discard(node)
                    removed += 1
        elif action.action_type in ("dedup", "stale_evals", "low_importance"):
            for mid in action.item_ids:
                did_remove = False
                if action.tier == "episodic":
                    did_remove = await mm.remove_episodic(mid)
                elif action.tier == "semantic":
                    did_remove = await mm.remove_semantic(mid)
                elif action.tier == "procedural":
                    did_remove = await mm.remove_procedural(mid)
                if did_remove:
                    removed += 1

    return removed
