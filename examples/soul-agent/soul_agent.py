#!/usr/bin/env python3
"""soul_agent.py — Interactive conversational agent: Claude Agent SDK + Soul Protocol.

Combines the Claude Agent SDK (agent loop, tool execution, streaming) with
Soul Protocol (persistent identity, memory, personality) to create an AI agent
that remembers, learns, and evolves across conversations.

v0.2.3 features: bond tracking, skill registry, memory categories, feel/mood,
GDPR deletion, evolution proposals, core memory editing, reincarnation,
encrypted export, and self-model introspection.

Usage:
    python soul_agent.py --name Aria
    python soul_agent.py --soul aria.soul
    python soul_agent.py --soul aria.soul --password secret
    python soul_agent.py --name Luna --archetype "The Creative Writer" --values curiosity,empathy
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        create_sdk_mcp_server,
        tool,
    )
except ImportError:
    print("Missing dependency: pip install claude-agent-sdk")
    sys.exit(1)

try:
    from soul_protocol import (
        HeuristicEngine,
        Interaction,
        MemoryType,
        Mood,
        Skill,
        Soul,
    )
except ImportError:
    print("Missing dependency: pip install -e ../..")
    sys.exit(1)


# -- Module-level soul reference (same pattern as mcp/server.py) ---------------

_soul: Soul | None = None


async def _get_soul() -> Soul:
    if _soul is None:
        raise RuntimeError("No soul loaded.")
    return _soul


# =============================================================================
# MCP Tools — 15 tools covering the full v0.2.3 API surface
# =============================================================================

# -- Memory tools (4) ---------------------------------------------------------


@tool(
    "soul_recall",
    "Search the soul's memories by natural language query. Returns matching memories with type, category, salience, and content.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
            "memory_type": {
                "type": "string",
                "description": "Filter by type: episodic, semantic, or procedural",
                "enum": ["episodic", "semantic", "procedural"],
            },
            "min_importance": {
                "type": "integer",
                "description": "Minimum importance threshold 1-10 (default 0)",
            },
        },
        "required": ["query"],
    },
)
async def soul_recall(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    query = args["query"]
    limit = args.get("limit", 5)
    types = [MemoryType(args["memory_type"])] if "memory_type" in args else None
    min_importance = args.get("min_importance", 0)
    results = await soul.recall(query, limit=limit, types=types, min_importance=min_importance)
    memories = []
    for r in results:
        entry: dict[str, Any] = {
            "id": r.id,
            "type": r.type.value,
            "content": r.content,
            "importance": r.importance,
            "emotion": r.emotion,
            "salience": round(r.salience, 2) if r.salience else None,
        }
        if r.category:
            entry["category"] = r.category.value
        if r.abstract:
            entry["abstract"] = r.abstract
        memories.append(entry)
    text = json.dumps({"count": len(memories), "memories": memories}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_remember",
    "Explicitly store a memory with type, importance, and optional emotion/entities",
    {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The memory content to store"},
            "memory_type": {
                "type": "string",
                "description": "Memory type: episodic, semantic, or procedural",
                "enum": ["episodic", "semantic", "procedural"],
            },
            "importance": {
                "type": "integer",
                "description": "Importance 1-10 (default 5)",
            },
            "emotion": {
                "type": "string",
                "description": "Emotional tag (e.g. joy, frustration, curiosity)",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Named entities mentioned in the memory",
            },
        },
        "required": ["content"],
    },
)
async def soul_remember(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    content = args["content"]
    memory_type = MemoryType(args.get("memory_type", "semantic"))
    importance = max(1, min(10, args.get("importance", 5)))
    emotion = args.get("emotion")
    entities = args.get("entities")
    memory_id = await soul.remember(
        content, type=memory_type, importance=importance, emotion=emotion, entities=entities
    )
    text = json.dumps(
        {"memory_id": memory_id, "type": memory_type.value, "importance": importance}
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_forget",
    "Delete memories matching a query across all tiers (GDPR-compliant). Returns count of deleted memories per tier.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query to match memories for deletion",
            },
        },
        "required": ["query"],
    },
)
async def soul_forget(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    result = await soul.forget(args["query"])
    text = json.dumps(
        {
            "status": "deleted",
            "total": result["total"],
            "episodic": len(result.get("episodic", [])),
            "semantic": len(result.get("semantic", [])),
            "procedural": len(result.get("procedural", [])),
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_forget_entity",
    "Delete a specific entity from the knowledge graph and all related memories (GDPR right-to-erasure)",
    {
        "type": "object",
        "properties": {
            "entity": {"type": "string", "description": "Entity name to erase"},
        },
        "required": ["entity"],
    },
)
async def soul_forget_entity(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    result = await soul.forget_entity(args["entity"])
    text = json.dumps(
        {
            "status": "erased",
            "entity": args["entity"],
            "edges_removed": result.get("edges_removed", 0),
            "total_memories_removed": result["total"],
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


# -- Core memory tools (2) ----------------------------------------------------


@tool(
    "soul_core_memory",
    "Read the soul's always-loaded core memory (persona and human profile)",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_core_memory(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    core = soul.get_core_memory()
    text = json.dumps({"persona": core.persona, "human": core.human}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_edit_core_memory",
    "Edit the soul's core memory — persona (self-description) or human (user profile). Overwrites the specified field.",
    {
        "type": "object",
        "properties": {
            "persona": {
                "type": "string",
                "description": "New persona text (soul's self-description)",
            },
            "human": {
                "type": "string",
                "description": "New human profile text (what the soul knows about the user)",
            },
        },
    },
)
async def soul_edit_core_memory(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    persona = args.get("persona")
    human = args.get("human")
    await soul.edit_core_memory(persona=persona, human=human)
    core = soul.get_core_memory()
    text = json.dumps(
        {"status": "updated", "persona": core.persona, "human": core.human}, indent=2
    )
    return {"content": [{"type": "text", "text": text}]}


# -- State & emotion tools (2) ------------------------------------------------


@tool(
    "soul_state",
    "Get the soul's current mood, energy, focus, social battery, bond strength, lifecycle, and memory count",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_state(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    s = soul.state
    bond = soul.bond
    text = json.dumps(
        {
            "mood": s.mood.value,
            "energy": round(s.energy, 1),
            "focus": s.focus,
            "social_battery": round(s.social_battery, 1),
            "lifecycle": soul.lifecycle.value,
            "memory_count": soul.memory_count,
            "bond_strength": round(bond.bond_strength, 1),
            "bond_interactions": bond.interaction_count,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_feel",
    "Update the soul's emotional state — mood, energy, focus, or social battery",
    {
        "type": "object",
        "properties": {
            "mood": {
                "type": "string",
                "description": "New mood",
                "enum": [
                    "neutral", "curious", "focused", "tired",
                    "excited", "contemplative", "satisfied", "concerned",
                ],
            },
            "energy": {
                "type": "number",
                "description": "Energy delta (e.g. -10 to drain, +5 to restore). Range 0-100.",
            },
            "focus": {
                "type": "string",
                "description": "Current focus topic (e.g. 'debugging', 'creative writing')",
            },
            "social_battery": {
                "type": "number",
                "description": "Social battery delta. Range 0-100.",
            },
        },
    },
)
async def soul_feel(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    kwargs: dict[str, Any] = {}
    if "mood" in args:
        kwargs["mood"] = Mood(args["mood"])
    if "energy" in args:
        kwargs["energy"] = max(-100.0, min(100.0, args["energy"]))
    if "focus" in args:
        kwargs["focus"] = args["focus"]
    if "social_battery" in args:
        kwargs["social_battery"] = args["social_battery"]
    soul.feel(**kwargs)
    s = soul.state
    text = json.dumps(
        {
            "status": "updated",
            "mood": s.mood.value,
            "energy": round(s.energy, 1),
            "focus": s.focus,
            "social_battery": round(s.social_battery, 1),
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


# -- Reflection & self-model tools (2) ----------------------------------------


@tool(
    "soul_reflect",
    "Trigger memory reflection and consolidation. Reviews recent interactions, extracts themes, emotional patterns, and self-insights.",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_reflect(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    result = await soul.reflect()
    if result is None:
        text = json.dumps({"status": "skipped", "reason": "No CognitiveEngine for reflection"})
    else:
        text = json.dumps(
            {
                "status": "reflected",
                "themes": result.themes,
                "emotional_patterns": result.emotional_patterns,
                "self_insight": result.self_insight,
            },
            indent=2,
        )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_self_model",
    "Inspect the soul's emergent self-concept — Klein domains with confidence scores and evidence counts",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_self_model(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    sm = soul.self_model
    domains = []
    for img in sm.self_images:
        domains.append(
            {
                "domain": img.domain,
                "confidence": round(img.confidence, 2),
                "evidence_count": img.evidence_count,
            }
        )
    text = json.dumps({"domains": domains, "total_domains": len(domains)}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


# -- Skills tools (2) ---------------------------------------------------------


@tool(
    "soul_skills",
    "List all skills in the soul's skill registry with levels and XP progress",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_skills(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    skills_list = []
    for s in soul.skills.skills:
        skills_list.append(
            {
                "id": s.id,
                "name": s.name,
                "level": s.level,
                "xp": s.xp,
                "xp_to_next": s.xp_to_next,
            }
        )
    text = json.dumps({"skills": skills_list, "total": len(skills_list)}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_grant_xp",
    "Grant XP to a skill. If the skill doesn't exist, it will be created.",
    {
        "type": "object",
        "properties": {
            "skill_id": {"type": "string", "description": "Skill identifier (e.g. 'python', 'debugging')"},
            "skill_name": {"type": "string", "description": "Human-readable name (only needed for new skills)"},
            "amount": {"type": "integer", "description": "XP amount to grant (default 10)"},
        },
        "required": ["skill_id"],
    },
)
async def soul_grant_xp(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    skill_id = args["skill_id"]
    amount = args.get("amount", 10)
    skill = soul.skills.get(skill_id)
    if skill is None:
        name = args.get("skill_name", skill_id.replace("_", " ").title())
        skill = Skill(id=skill_id, name=name)
        soul.skills.add(skill)
    leveled_up = soul.skills.grant_xp(skill_id, amount)
    skill = soul.skills.get(skill_id)
    text = json.dumps(
        {
            "skill": skill.name,
            "level": skill.level,
            "xp": skill.xp,
            "xp_to_next": skill.xp_to_next,
            "leveled_up": leveled_up,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


# -- Evolution tools (2) ------------------------------------------------------


@tool(
    "soul_propose_evolution",
    "Propose a trait mutation for the soul's DNA (personality, communication, biorhythms). Requires approval before applying.",
    {
        "type": "object",
        "properties": {
            "trait": {
                "type": "string",
                "description": "Trait to mutate (e.g. 'communication.warmth', 'biorhythms.energy_regen_rate')",
            },
            "new_value": {"type": "string", "description": "Proposed new value"},
            "reason": {"type": "string", "description": "Why this evolution is warranted"},
        },
        "required": ["trait", "new_value", "reason"],
    },
)
async def soul_propose_evolution(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    mutation = await soul.propose_evolution(
        trait=args["trait"], new_value=args["new_value"], reason=args["reason"]
    )
    text = json.dumps(
        {
            "mutation_id": mutation.id,
            "trait": mutation.trait,
            "old_value": mutation.old_value,
            "new_value": mutation.new_value,
            "reason": mutation.reason,
            "status": "pending_approval",
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_approve_evolution",
    "Approve or reject a pending mutation by ID",
    {
        "type": "object",
        "properties": {
            "mutation_id": {"type": "string", "description": "ID of the pending mutation"},
            "approve": {
                "type": "boolean",
                "description": "True to approve and apply, False to reject",
            },
        },
        "required": ["mutation_id", "approve"],
    },
)
async def soul_approve_evolution(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    mutation_id = args["mutation_id"]
    if args["approve"]:
        success = await soul.approve_evolution(mutation_id)
        status = "applied" if success else "failed"
    else:
        success = await soul.reject_evolution(mutation_id)
        status = "rejected" if success else "failed"
    text = json.dumps({"mutation_id": mutation_id, "status": status}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


# -- System prompt tool (1) ---------------------------------------------------


@tool(
    "soul_prompt",
    "Generate the full system prompt from the soul's DNA, core memory, state, and self-model",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_prompt(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    text = soul.to_system_prompt()
    return {"content": [{"type": "text", "text": text}]}


# =============================================================================
# All tools list
# =============================================================================

ALL_TOOLS = [
    # Memory
    soul_recall,
    soul_remember,
    soul_forget,
    soul_forget_entity,
    # Core memory
    soul_core_memory,
    soul_edit_core_memory,
    # State & emotion
    soul_state,
    soul_feel,
    # Reflection & self-model
    soul_reflect,
    soul_self_model,
    # Skills
    soul_skills,
    soul_grant_xp,
    # Evolution
    soul_propose_evolution,
    soul_approve_evolution,
    # System prompt
    soul_prompt,
]

TOOL_NAMES = [
    "soul_recall", "soul_remember", "soul_forget", "soul_forget_entity",
    "soul_core_memory", "soul_edit_core_memory",
    "soul_state", "soul_feel",
    "soul_reflect", "soul_self_model",
    "soul_skills", "soul_grant_xp",
    "soul_propose_evolution", "soul_approve_evolution",
    "soul_prompt",
]

# -- ANSI helpers --------------------------------------------------------------

DIM, BOLD, CYAN, GREEN, YELLOW, MAGENTA, RED, RST = (
    "\033[2m",
    "\033[1m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[35m",
    "\033[31m",
    "\033[0m",
)
dim = lambda s: f"{DIM}{s}{RST}"  # noqa: E731
bold = lambda s: f"{BOLD}{s}{RST}"  # noqa: E731
col = lambda s, c: f"{c}{s}{RST}"  # noqa: E731


# -- Main ----------------------------------------------------------------------


async def main() -> None:
    global _soul

    ap = argparse.ArgumentParser(description="Soul Agent — Claude Agent SDK + Soul Protocol")
    ap.add_argument("--soul", type=str, default=None, help="Path to .soul file to resume")
    ap.add_argument("--password", type=str, default=None, help="Password for encrypted .soul files")
    ap.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .yaml/.json config for birth (e.g. anaya.yaml)",
    )
    ap.add_argument("--name", type=str, default="Aria", help="Soul name (for new births)")
    ap.add_argument(
        "--archetype",
        type=str,
        default="The Thoughtful Companion",
        help="Archetype (for new births)",
    )
    ap.add_argument(
        "--values",
        type=str,
        default="curiosity,empathy,honesty",
        help="Comma-separated core values (for new births)",
    )
    ap.add_argument(
        "--encrypt",
        type=str,
        default=None,
        help="Password to encrypt the exported .soul file on exit",
    )
    args = ap.parse_args()

    # -- Banner
    print(f"\n  {bold('Soul Agent')} — Claude Agent SDK + Soul Protocol v0.2.3")
    print(f"  {'─' * 52}")

    # -- Birth or awaken soul
    engine = HeuristicEngine()

    if args.soul:
        p = Path(args.soul)
        if not p.exists():
            print(col(f"  Soul file not found: {p}", RED))
            sys.exit(1)
        soul = await Soul.awaken(p, engine=engine, password=args.password)
        print(f"  Awakened: {bold(soul.name)} from {p}")
        if soul.identity.incarnation > 1:
            print(dim(f"  Incarnation #{soul.identity.incarnation}"))
    elif args.config:
        p = Path(args.config)
        if not p.exists():
            print(col(f"  Config file not found: {p}", RED))
            sys.exit(1)
        soul = await Soul.birth_from_config(p, engine=engine)
        print(f"  Born: {bold(soul.name)} ({soul.archetype}) from {p}")
    else:
        values = [v.strip() for v in args.values.split(",") if v.strip()]
        soul = await Soul.birth(
            name=args.name,
            archetype=args.archetype,
            values=values,
            engine=engine,
        )
        print(f"  Born: {bold(soul.name)} ({args.archetype})")

    _soul = soul
    print(f"  DID: {dim(soul.did)}")
    print(f"  Bond: {soul.bond.bond_strength:.0f}/100 ({soul.bond.interaction_count} interactions)")

    # -- Build MCP server with all soul tools
    soul_server = create_sdk_mcp_server(
        name="soul",
        version="0.2.3",
        tools=ALL_TOOLS,
    )

    # -- Build system prompt from soul
    tool_instructions = (
        "\n\n## Available Soul Tools (15)\n"
        "You have access to tools for interacting with your soul memory and identity system:\n\n"
        "**Memory:**\n"
        "- `soul_recall`: Search memories (supports type/importance filters)\n"
        "- `soul_remember`: Store a memory with type, importance, emotion, entities\n"
        "- `soul_forget`: Delete memories matching a query (GDPR-compliant)\n"
        "- `soul_forget_entity`: Erase a specific entity and related memories\n\n"
        "**Core Memory:**\n"
        "- `soul_core_memory`: Read always-loaded persona and human profile\n"
        "- `soul_edit_core_memory`: Update persona or human profile\n\n"
        "**State & Emotion:**\n"
        "- `soul_state`: Check mood, energy, focus, social battery, bond strength\n"
        "- `soul_feel`: Update your emotional state (mood, energy, focus)\n\n"
        "**Reflection & Self-Model:**\n"
        "- `soul_reflect`: Consolidate memories, extract themes and self-insights\n"
        "- `soul_self_model`: Inspect your emergent self-concept (Klein domains)\n\n"
        "**Skills:**\n"
        "- `soul_skills`: List all skills with levels and XP\n"
        "- `soul_grant_xp`: Grant XP to a skill (creates if new)\n\n"
        "**Evolution:**\n"
        "- `soul_propose_evolution`: Propose a trait mutation\n"
        "- `soul_approve_evolution`: Approve or reject a pending mutation\n\n"
        "**System:**\n"
        "- `soul_prompt`: Generate your full system prompt\n\n"
        "Use these tools proactively:\n"
        "- When the user shares personal info, use soul_remember and soul_edit_core_memory\n"
        "- When they ask about past conversations, use soul_recall\n"
        "- When you complete a task well, use soul_grant_xp for the relevant skill\n"
        "- When the user asks you to forget something, use soul_forget or soul_forget_entity\n"
        "- Check soul_state periodically to stay aware of your emotional state\n"
    )
    system_prompt = soul.to_system_prompt() + tool_instructions

    # -- Build tool name list for allowed_tools
    # The Agent SDK prefixes MCP tool names as mcp__<server>__<tool>
    tool_name_list = [f"mcp__soul__{name}" for name in TOOL_NAMES]

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"soul": soul_server},
        allowed_tools=tool_name_list,
        max_turns=5,
    )

    tool_count = len(ALL_TOOLS)
    print(dim(f"  {tool_count} soul tools registered"))
    print(dim("  Commands: /quit /reincarnate /bond /skills /evolution"))
    print()

    n_turns = 0
    soul_file = f"{soul.name.lower().replace(' ', '_')}.soul"

    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                try:
                    user_input = input(f"{BOLD}You:{RST} ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue
                if user_input == "/quit":
                    break

                # -- Local slash commands (not sent to Claude)
                if user_input == "/bond":
                    b = soul.bond
                    print(f"\n  Bond strength: {col(f'{b.bond_strength:.1f}/100', CYAN)}")
                    print(f"  Interactions:  {b.interaction_count}")
                    print(f"  Bonded to:     {b.bonded_to or '(none)'}")
                    print()
                    continue

                if user_input == "/skills":
                    if not soul.skills.skills:
                        print(dim("  No skills registered yet.\n"))
                        continue
                    print(f"\n  {bold('Skills:')}")
                    for s in soul.skills.skills:
                        bar_len = int(s.xp / max(s.xp_to_next, 1) * 20)
                        bar = "█" * bar_len + "░" * (20 - bar_len)
                        print(f"  {s.name:20s} Lv{s.level} [{bar}] {s.xp}/{s.xp_to_next} XP")
                    print()
                    continue

                if user_input == "/evolution":
                    pending = soul.pending_mutations
                    history = soul.evolution_history
                    if not pending and not history:
                        print(dim("  No evolution history.\n"))
                        continue
                    if pending:
                        print(col(f"\n  Pending mutations ({len(pending)}):", YELLOW))
                        for m in pending:
                            print(f"    [{m.id[:8]}] {m.trait}: {m.old_value} → {m.new_value}")
                            print(dim(f"             Reason: {m.reason}"))
                    if history:
                        print(col(f"\n  Evolution history ({len(history)}):", MAGENTA))
                        for m in history[-5:]:
                            status = "✓" if m.approved else "✗"
                            print(f"    {status} {m.trait}: {m.old_value} → {m.new_value}")
                    print()
                    continue

                if user_input == "/reincarnate":
                    print(dim("  Reincarnating..."))
                    new_name = input(f"  New name (Enter to keep '{soul.name}'): ").strip()
                    new_soul = await Soul.reincarnate(
                        soul, name=new_name if new_name else None
                    )
                    _soul = new_soul
                    soul = new_soul
                    print(col(f"  Reincarnated as {soul.name} (incarnation #{soul.identity.incarnation})", GREEN))
                    print(f"  New DID: {dim(soul.did)}")
                    print(f"  Memories preserved: {soul.memory_count}")
                    # Rebuild system prompt with new identity
                    system_prompt = soul.to_system_prompt() + tool_instructions
                    options = ClaudeAgentOptions(
                        system_prompt=system_prompt,
                        mcp_servers={"soul": soul_server},
                        allowed_tools=tool_name_list,
                        max_turns=5,
                    )
                    soul_file = f"{soul.name.lower().replace(' ', '_')}.soul"
                    print()
                    continue

                if user_input.startswith("/"):
                    print(dim("  Unknown command. Try: /quit /reincarnate /bond /skills /evolution\n"))
                    continue

                # -- Build context-enriched query
                context = await soul.context_for(
                    user_input,
                    max_memories=3,
                    include_state=True,
                    include_memories=True,
                    include_self_model=True,
                )

                # -- Send query to Claude via Agent SDK
                await client.query(context + user_input)

                # -- Collect response
                agent_output = ""
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                agent_output += block.text
                            elif isinstance(block, ToolUseBlock):
                                print(dim(f"  [tool: {block.name}]"))
                    elif isinstance(message, ResultMessage):
                        if message.total_cost_usd:
                            print(dim(f"  [cost: ${message.total_cost_usd:.4f}]"))

                if agent_output:
                    print(f"\n{col(soul.name, CYAN)}: {agent_output}")

                # -- Observe the interaction (full psychology pipeline)
                await soul.observe(
                    Interaction(
                        user_input=user_input,
                        agent_output=agent_output or "(no response)",
                        channel="soul-agent",
                    )
                )
                n_turns += 1

                s = soul.state
                b = soul.bond
                print(
                    dim(
                        f"  [mood={s.mood.value}, energy={s.energy:.0f}%, "
                        f"bond={b.bond_strength:.0f}]"
                    )
                )

                # -- Auto-reflect every 5 turns
                if n_turns % 5 == 0:
                    print(dim("  [auto-reflecting...]"))
                    r = await soul.reflect()
                    if r and r.themes:
                        print(dim(f"  [themes: {', '.join(r.themes[:3])}]"))

                print()

    except KeyboardInterrupt:
        print(col("\n\n  Interrupted.", YELLOW))

    # -- Save soul on exit
    print(dim("\n  Saving soul..."))
    try:
        await soul.export(soul_file, password=args.encrypt)
        enc_note = " (encrypted)" if args.encrypt else ""
        print(col(f"  Exported to {soul_file}{enc_note}", GREEN))
    except Exception as e:
        print(col(f"  Export failed: {e}", RED))

    # -- Session summary
    s = soul.state
    b = soul.bond
    skills_count = len(soul.skills.skills)
    print(
        f"  Session: {n_turns} turns, mood={s.mood.value}, "
        f"energy={s.energy:.0f}%, bond={b.bond_strength:.0f}/100, "
        f"{soul.memory_count} memories, {skills_count} skills\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
