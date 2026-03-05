#!/usr/bin/env python3
"""soul_agent.py — Interactive conversational agent: Claude Agent SDK + Soul Protocol.

Combines the Claude Agent SDK (agent loop, tool execution, streaming) with
Soul Protocol (persistent identity, memory, personality) to create an AI agent
that remembers, learns, and evolves across conversations.

Usage:
    python soul_agent.py --name Aria
    python soul_agent.py --soul aria.soul
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


# -- Custom MCP tools (4) wrapping soul operations ----------------------------


@tool(
    "soul_recall",
    "Search the soul's memories by natural language query",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
)
async def soul_recall(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    query = args["query"]
    limit = args.get("limit", 5)
    results = await soul.recall(query, limit=limit)
    memories = [
        {
            "type": r.type.value,
            "content": r.content,
            "importance": r.importance,
            "emotion": r.emotion,
        }
        for r in results
    ]
    text = json.dumps({"count": len(memories), "memories": memories}, indent=2)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_state",
    "Get the soul's current mood, energy, focus, and social battery",
    {
        "type": "object",
        "properties": {},
    },
)
async def soul_state(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    s = soul.state
    text = json.dumps(
        {
            "mood": s.mood.value,
            "energy": round(s.energy, 1),
            "focus": s.focus,
            "social_battery": round(s.social_battery, 1),
            "lifecycle": soul.lifecycle.value,
        },
        indent=2,
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "soul_reflect",
    "Trigger memory reflection and consolidation",
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
    "soul_remember",
    "Explicitly store a memory",
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
        },
        "required": ["content"],
    },
)
async def soul_remember(args: dict[str, Any]) -> dict[str, Any]:
    soul = await _get_soul()
    content = args["content"]
    memory_type = MemoryType(args.get("memory_type", "semantic"))
    importance = max(1, min(10, args.get("importance", 5)))
    memory_id = await soul.remember(content, type=memory_type, importance=importance)
    text = json.dumps(
        {
            "memory_id": memory_id,
            "type": memory_type.value,
            "importance": importance,
        }
    )
    return {"content": [{"type": "text", "text": text}]}


# -- ANSI helpers --------------------------------------------------------------

DIM, BOLD, CYAN, GREEN, YELLOW, RED, RST = (
    "\033[2m",
    "\033[1m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
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
    ap.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .yaml/.json config for birth (e.g. rohit.yaml)",
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
    args = ap.parse_args()

    # -- Banner
    print(f"\n  {bold('Soul Agent')} — Claude Agent SDK + Soul Protocol")
    print(f"  {'-' * 47}")

    # -- Birth or awaken soul
    engine = HeuristicEngine()

    if args.soul:
        p = Path(args.soul)
        if not p.exists():
            print(col(f"  Soul file not found: {p}", RED))
            sys.exit(1)
        soul = await Soul.awaken(p, engine=engine)
        print(f"  Awakened: {bold(soul.name)} from {p}")
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

    # -- Build MCP server with soul tools
    soul_server = create_sdk_mcp_server(
        name="soul",
        version="1.0.0",
        tools=[soul_recall, soul_state, soul_reflect, soul_remember],
    )

    # -- Build system prompt from soul
    tool_instructions = (
        "\n\n## Available Soul Tools\n"
        "You have access to tools for interacting with your soul memory system:\n"
        "- `soul_recall`: Search your memories for relevant information\n"
        "- `soul_state`: Check your current mood, energy, and social battery\n"
        "- `soul_reflect`: Consolidate and reflect on recent memories\n"
        "- `soul_remember`: Explicitly store an important memory\n\n"
        "Use these tools proactively. When the user shares personal information, "
        "use soul_remember to store it. When they ask about past conversations, "
        "use soul_recall to search your memories. Check soul_state periodically "
        "to stay aware of your emotional state."
    )
    system_prompt = soul.to_system_prompt() + tool_instructions

    # -- Configure Agent SDK client
    soul_tool_names = [
        "mcp__soul__soul_recall",
        "mcp__soul__soul_state",
        "mcp__soul__soul_reflect",
        "mcp__soul__soul_remember",
    ]
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"soul": soul_server},
        allowed_tools=soul_tool_names,
        max_turns=3,
    )

    print(dim("  Tools: soul_recall, soul_state, soul_reflect, soul_remember"))
    print(dim("  Type /quit to save and exit\n"))

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

                # -- Build context-enriched query
                # Inject live soul state + relevant memories so the agent
                # stays grounded even as conversation context gets compressed
                context = await soul.context_for(user_input, max_memories=3)

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

                # -- Observe the interaction (psychology pipeline)
                await soul.observe(
                    Interaction(
                        user_input=user_input,
                        agent_output=agent_output or "(no response)",
                        channel="soul-agent",
                    )
                )
                n_turns += 1

                s = soul.state
                print(dim(f"  [mood={s.mood.value}, energy={s.energy:.0f}%]"))

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
        await soul.export(soul_file)
        print(col(f"  Exported to {soul_file}", GREEN))
    except Exception as e:
        print(col(f"  Export failed: {e}", RED))

    s = soul.state
    print(
        f"  Session: {n_turns} turns, mood={s.mood.value}, "
        f"energy={s.energy:.0f}%, {soul.memory_count} memories\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
