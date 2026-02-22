# soul_protocol.mcp.server — FastMCP server for soul-protocol
# 10 tools, 3 resources, 2 prompts for AI agent integration
#
# Updated: Added _soul_path tracking for save round-trips,
#          path validation on soul_export, soul_birth replacement warning
#
# Usage:
#   SOUL_PATH=aria.soul soul-mcp
#   Or call soul_birth to create a new soul at runtime

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP  # optional dep: pip install soul-protocol[mcp]

from ..soul import Soul
from ..types import Interaction, MemoryType, Mood

mcp = FastMCP("soul-protocol", instructions="Soul Protocol MCP server. Provides persistent AI identity and memory.")

_soul: Soul | None = None
_soul_path: str | None = None


async def _get_soul() -> Soul:
    """Get the active soul, raising if none loaded."""
    if _soul is None:
        raise RuntimeError("No soul loaded. Call soul_birth first or set SOUL_PATH env var.")
    return _soul


# --- Tools (10) ---


@mcp.tool
async def soul_birth(name: str, archetype: str = "", values: list[str] | None = None) -> str:
    """Create a new soul with persistent identity and memory.

    Args:
        name: The soul's name
        archetype: Optional archetype (e.g. "The Compassionate Creator")
        values: Optional list of core values
    """
    global _soul, _soul_path
    replaced = _soul is not None
    soul = await Soul.birth(name, archetype=archetype, values=values or [])
    _soul = soul
    _soul_path = None  # new soul has no file path yet
    result: dict[str, Any] = {"name": soul.name, "did": soul.did, "status": "born"}
    if replaced:
        result["warning"] = "An existing soul was replaced. Call soul_save first to preserve it."
    return json.dumps(result)


@mcp.tool
async def soul_observe(user_input: str, agent_output: str, channel: str = "mcp") -> str:
    """Process an interaction through the psychology pipeline.
    Extracts facts, detects sentiment, updates self-model.

    Args:
        user_input: What the user said
        agent_output: What the agent responded
        channel: Source channel identifier
    """
    soul = await _get_soul()
    await soul.observe(Interaction(user_input=user_input, agent_output=agent_output, channel=channel))
    state = soul.state
    return json.dumps({
        "status": "observed",
        "mood": state.mood.value,
        "energy": round(state.energy, 1),
    })


@mcp.tool
async def soul_remember(content: str, importance: int = 5, memory_type: str = "semantic", emotion: str | None = None) -> str:
    """Store a memory directly.

    Args:
        content: The memory content
        importance: 1-10 scale
        memory_type: One of: core, episodic, semantic, procedural
        emotion: Optional emotion label
    """
    soul = await _get_soul()
    mt = MemoryType(memory_type)
    memory_id = await soul.remember(content, type=mt, importance=importance, emotion=emotion)
    return json.dumps({"memory_id": memory_id, "type": memory_type, "importance": importance})


@mcp.tool
async def soul_recall(query: str, limit: int = 5) -> str:
    """Search the soul's memories by natural language query.

    Args:
        query: Search query
        limit: Maximum results to return
    """
    soul = await _get_soul()
    results = await soul.recall(query, limit=limit)
    memories = []
    for r in results:
        memories.append({
            "id": r.id,
            "type": r.type.value,
            "content": r.content,
            "importance": r.importance,
            "emotion": r.emotion,
        })
    return json.dumps({"count": len(memories), "memories": memories})


@mcp.tool
async def soul_reflect() -> str:
    """Trigger memory reflection and consolidation.
    Identifies themes, summarizes patterns, generates self-insights.
    Requires CognitiveEngine for full power; returns None without one.
    """
    soul = await _get_soul()
    result = await soul.reflect()
    if result is None:
        return json.dumps({"status": "skipped", "reason": "No CognitiveEngine available for reflection"})
    return json.dumps({
        "status": "reflected",
        "themes": result.themes,
        "emotional_patterns": result.emotional_patterns,
        "self_insight": result.self_insight,
    })


@mcp.tool
async def soul_state() -> str:
    """Get the soul's current mood, energy, focus, and social battery."""
    soul = await _get_soul()
    s = soul.state
    return json.dumps({
        "mood": s.mood.value,
        "energy": round(s.energy, 1),
        "focus": s.focus,
        "social_battery": round(s.social_battery, 1),
        "lifecycle": soul.lifecycle.value,
    })


@mcp.tool
async def soul_feel(mood: str | None = None, energy: float | None = None) -> str:
    """Update the soul's emotional state.

    Args:
        mood: One of: neutral, curious, focused, tired, excited, contemplative, satisfied, concerned
        energy: Energy delta (-100 to 100). Positive increases, negative decreases. Clamped to 0-100.
    """
    soul = await _get_soul()
    kwargs: dict[str, Any] = {}
    if mood is not None:
        kwargs["mood"] = Mood(mood)
    if energy is not None:
        kwargs["energy"] = energy
    # feel() is synchronous in the Soul API
    soul.feel(**kwargs)
    s = soul.state
    return json.dumps({"mood": s.mood.value, "energy": round(s.energy, 1)})


@mcp.tool
async def soul_prompt() -> str:
    """Generate the complete system prompt for LLM injection.
    Includes DNA, identity, core memory, current state, and self-model.
    """
    soul = await _get_soul()
    return soul.to_system_prompt()


@mcp.tool
async def soul_save(path: str | None = None) -> str:
    """Persist the soul to disk as YAML config.

    Args:
        path: File path to save to. If omitted, saves to the original SOUL_PATH
              location (or ~/.soul/<soul_id>/ if no path is known).
    """
    soul = await _get_soul()
    save_path = path or _soul_path
    await soul.save(save_path)
    return json.dumps({"status": "saved", "path": save_path or "~/.soul/", "name": soul.name})


@mcp.tool
async def soul_export(path: str) -> str:
    """Export the soul as a portable .soul file (zip archive).
    Contains identity, memory, state, and self-model.

    Args:
        path: Output file path (must end in .soul)
    """
    soul = await _get_soul()
    resolved = Path(path).resolve()
    if resolved.suffix != ".soul":
        raise ValueError(f"Export path must end in .soul, got: {path!r}")
    await soul.export(resolved)
    return json.dumps({"status": "exported", "path": str(resolved), "name": soul.name})


# --- Resources (3) ---


@mcp.resource("soul://identity")
async def soul_identity_resource() -> str:
    """Full identity JSON including DID, name, archetype, values, and origin."""
    soul = await _get_soul()
    identity = soul.identity
    return json.dumps({
        "did": identity.did,
        "name": identity.name,
        "archetype": identity.archetype,
        "born": identity.born.isoformat(),
        "bonded_to": identity.bonded_to,
        "core_values": identity.core_values,
        "origin_story": identity.origin_story,
    })


@mcp.resource("soul://memory/core")
async def soul_core_memory_resource() -> str:
    """Core memory: persona definition and human knowledge."""
    soul = await _get_soul()
    core = soul.get_core_memory()
    return json.dumps({"persona": core.persona, "human": core.human})


@mcp.resource("soul://state")
async def soul_state_resource() -> str:
    """Current soul state: mood, energy, focus, social battery."""
    soul = await _get_soul()
    s = soul.state
    return json.dumps({
        "mood": s.mood.value,
        "energy": round(s.energy, 1),
        "focus": s.focus,
        "social_battery": round(s.social_battery, 1),
        "lifecycle": soul.lifecycle.value,
    })


# --- Prompts (2) ---


@mcp.prompt
def soul_system_prompt() -> str:
    """Complete system prompt for LLM context injection.
    Includes DNA, identity, core memory, current state, and self-model.
    """
    if _soul is None:
        return "No soul loaded. Call soul_birth first."
    return _soul.to_system_prompt()


@mcp.prompt
def soul_introduction() -> str:
    """First-person self-introduction from the soul's perspective."""
    if _soul is None:
        return "No soul loaded. Call soul_birth first."
    s = _soul
    values = ", ".join(s.identity.core_values) if s.identity.core_values else "not yet defined"
    return (
        f"I'm {s.name}"
        + (f", {s.identity.archetype}" if s.identity.archetype else "")
        + f". My core values are {values}."
        + f" I'm currently feeling {s.state.mood.value} with {s.state.energy:.0f}% energy."
    )


# --- Server lifecycle ---


def create_server() -> FastMCP:
    """Create and return the FastMCP server instance."""
    return mcp


def run_server() -> None:
    """Entry point for the soul-mcp console script."""
    import asyncio

    global _soul_path
    path = os.environ.get("SOUL_PATH")
    if path:
        _soul_path = path

        async def _load() -> None:
            global _soul
            _soul = await Soul.awaken(path)

        asyncio.run(_load())

    mcp.run()
