# real_agent.py — Interactive conversational agent powered by Soul Protocol.
#
# Demonstrates the full soul lifecycle: birth -> observe -> recall -> reflect -> save.
# Multi-engine support (Claude, OpenAI, Ollama, heuristic) with dual-model architecture:
# cheap/fast models for soul cognition, better models for user-facing chat.
#
# Usage:
#   python examples/real_agent.py --engine claude
#   python examples/real_agent.py --engine openai
#   python examples/real_agent.py --engine ollama --soul aria.soul
#   python examples/real_agent.py --engine heuristic

from __future__ import annotations

import argparse  # noqa: E401
import asyncio
import os
import sys
from pathlib import Path

from soul_protocol import HeuristicEngine, Interaction, Soul

# -- ANSI helpers (zero deps) ------------------------------------------------
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

# -- Engine implementations --------------------------------------------------


class ClaudeEngine:
    """Anthropic: haiku for think(), sonnet for chat()."""

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError:
            sys.exit(col("Missing dep: pip install anthropic", RED))
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            sys.exit(col("Set ANTHROPIC_API_KEY env var.", RED))
        self._c = anthropic.Anthropic(api_key=key)
        self._think, self._chat_model = "claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250514"

    def _call(self, model: str, prompt: str, *, system: str = "") -> str:
        kw: dict = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kw["system"] = system
        return self._c.messages.create(**kw).content[0].text

    async def think(self, prompt: str) -> str:
        return await asyncio.to_thread(self._call, self._think, prompt)

    async def chat(self, system: str, user_msg: str) -> str:
        return await asyncio.to_thread(self._call, self._chat_model, user_msg, system=system)


class OpenAIEngine:
    """OpenAI: gpt-4o-mini for think(), gpt-4o for chat()."""

    def __init__(self) -> None:
        try:
            import openai
        except ImportError:
            sys.exit(col("Missing dep: pip install openai", RED))
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            sys.exit(col("Set OPENAI_API_KEY env var.", RED))
        self._c = openai.OpenAI(api_key=key)
        self._think, self._chat_model = "gpt-4o-mini", "gpt-4o"

    def _call(self, model: str, system: str, user_msg: str) -> str:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_msg})
        return (
            self._c.chat.completions.create(model=model, messages=msgs, max_tokens=1024)
            .choices[0]
            .message.content
            or ""
        )

    async def think(self, prompt: str) -> str:
        return await asyncio.to_thread(self._call, self._think, "", prompt)

    async def chat(self, system: str, user_msg: str) -> str:
        return await asyncio.to_thread(self._call, self._chat_model, system, user_msg)


class OllamaEngine:
    """Local Ollama: same model for think() and chat()."""

    def __init__(self, model: str = "llama3.2") -> None:
        try:
            import httpx  # noqa: F401
        except ImportError:
            sys.exit(col("Missing dep: pip install httpx", RED))
        self._model = model
        self._url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    async def _call(self, system: str, user_msg: str) -> str:
        import httpx

        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_msg})
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{self._url}/api/chat",
                json={"model": self._model, "messages": msgs, "stream": False},
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def think(self, prompt: str) -> str:
        return await self._call("", prompt)

    async def chat(self, system: str, user_msg: str) -> str:
        return await self._call(system, user_msg)


class HeuristicChatEngine(HeuristicEngine):
    """No-LLM echo mode for testing."""

    async def chat(self, system: str, user_msg: str) -> str:
        return f"[echo] I heard you say: {user_msg}"


ENGINE_LABELS = {
    "claude": "claude (haiku-4.5 for cognition, sonnet-4.5 for chat)",
    "openai": "openai (gpt-4o-mini for cognition, gpt-4o for chat)",
    "ollama": "ollama (local model for both)",
    "heuristic": "heuristic (no LLM, echo mode)",
}


def build_engine(name: str):
    """Factory: returns the engine for the given CLI flag."""
    return {"claude": ClaudeEngine, "openai": OpenAIEngine, "ollama": OllamaEngine}.get(
        name, HeuristicChatEngine
    )()


def mem_stats(soul: Soul) -> dict[str, int]:
    """Memory count by type (reaches into internals)."""
    m = soul._memory  # noqa: SLF001
    return {
        "episodic": len(m._episodic._memories),
        "semantic": len(m._semantic._facts),
        "procedural": len(m._procedural._procedures),
    }


# -- Slash command handlers --------------------------------------------------
async def cmd_recall(soul: Soul, arg: str) -> None:
    query = arg.strip()
    if not query:
        print(dim("  Usage: /recall <query>"))
        return
    memories = await soul.recall(query, limit=5)
    if memories:
        print(col(f"\n  Memories matching '{query}':", YELLOW))
        for m in memories:
            emo = f" ({m.emotion})" if m.emotion else ""
            print(f"  - [{m.type.value}] {m.content}{emo}")
    else:
        print(dim(f"  No memories matching '{query}'"))


async def cmd_state(soul: Soul) -> None:
    s = soul.state
    print(f"\n  Mood:           {col(s.mood.value, CYAN)}")
    print(f"  Energy:         {s.energy:.0f}%")
    print(f"  Focus:          {s.focus}")
    print(f"  Social Battery: {s.social_battery:.0f}%")
    print(f"  Lifecycle:      {soul.lifecycle.value}")


async def cmd_reflect(soul: Soul) -> None:
    print(dim("  Reflecting..."))
    result = await soul.reflect()
    if result:
        if result.themes:
            print(col("  Themes:", MAGENTA))
            for t in result.themes:
                print(f"    - {t}")
        if result.emotional_patterns:
            print(col(f"  Emotional patterns: {result.emotional_patterns}", MAGENTA))
        if result.self_insight:
            print(col(f"  Self-insight: {result.self_insight}", MAGENTA))
    else:
        print(dim("  No reflection produced (heuristic mode or no episodes)."))


async def cmd_memories(soul: Soul) -> None:
    stats = mem_stats(soul)
    total = sum(stats.values())
    print(f"\n  Memory stats ({total} total):")
    for t, c in stats.items():
        print(f"    {t:12s}: {c}")


async def cmd_save(soul: Soul, arg: str) -> None:
    path = arg.strip() or None
    print(dim("  Saving..."))
    await soul.save(path)
    print(col("  Soul saved.", GREEN))


async def cmd_export(soul: Soul, arg: str, default: str) -> None:
    path = arg.strip() or default
    print(dim("  Exporting..."))
    await soul.export(path)
    print(col(f"  Exported to {path}", GREEN))


# -- Main loop ---------------------------------------------------------------
async def main() -> None:
    ap = argparse.ArgumentParser(description="Soul Protocol -- Real Agent Demo")
    ap.add_argument(
        "--engine", choices=["claude", "openai", "ollama", "heuristic"], default="claude"
    )
    ap.add_argument("--soul", type=str, default=None, help="Path to .soul file to load")
    ap.add_argument("--name", type=str, default="Aria", help="Soul name for new births")
    args = ap.parse_args()

    engine = build_engine(args.engine)

    # -- Banner
    print(f"\n  {bold('Soul Protocol')} -- Real Agent Demo")
    print(f"  {'─' * 37}")

    # -- Birth or awaken
    if args.soul:
        p = Path(args.soul)
        if not p.exists():
            sys.exit(col(f"  Soul file not found: {p}", RED))
        soul = await Soul.awaken(p, engine=engine)
        print(f"  Awakened soul: {bold(soul.name)} from {p}")
    else:
        soul = await Soul.birth(
            name=args.name,
            archetype="The Thoughtful Companion",
            values=["curiosity", "empathy", "honesty"],
            engine=engine,
        )
        print(f"  Birthing soul: {bold(soul.name)} (The Thoughtful Companion)")

    print(f"  Engine: {ENGINE_LABELS[args.engine]}")
    print(f"  DID: {dim(soul.did)}\n")
    print(dim("  Commands: /recall /state /reflect /memories /save /export /quit\n"))

    n_interactions = 0
    soul_file = f"{soul.name.lower()}.soul"

    try:
        while True:
            try:
                user_input = input(f"{BOLD}You:{RST} ").strip()
            except EOFError:
                break
            if not user_input:
                continue

            # -- Dispatch slash commands
            if user_input.startswith("/recall "):
                await cmd_recall(soul, user_input[8:])
                print()
                continue
            if user_input == "/state":
                await cmd_state(soul)
                print()
                continue
            if user_input == "/reflect":
                await cmd_reflect(soul)
                print()
                continue
            if user_input == "/memories":
                await cmd_memories(soul)
                print()
                continue
            if user_input.startswith("/save"):
                await cmd_save(soul, user_input[5:])
                print()
                continue
            if user_input.startswith("/export"):
                await cmd_export(soul, user_input[7:], soul_file)
                print()
                continue
            if user_input == "/quit":
                break
            if user_input.startswith("/"):
                print(
                    dim(
                        "  Unknown command. Try: /recall /state /reflect /memories /save /export /quit\n"
                    )
                )
                continue

            # -- Conversation turn
            # 1. Recall relevant memories
            memories = await soul.recall(user_input, limit=3)
            print(
                dim(f"\n  [Recalled {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}]")
            )

            # 2. Build system prompt with soul identity + recalled memories
            sys_prompt = soul.to_system_prompt()
            if memories:
                sys_prompt += "\n\n## Relevant Memories\n"
                for m in memories:
                    sys_prompt += f"- [{m.type.value}] {m.content}\n"

            # 3. Generate response via LLM
            try:
                response = await engine.chat(sys_prompt, user_input)
            except Exception as e:
                print(col(f"  LLM error: {e}", RED))
                print()
                continue

            print(f"\n{col(soul.name, CYAN)}: {response}")

            # 4. Observe the interaction (soul processes sentiment, facts, entities)
            await soul.observe(
                Interaction(user_input=user_input, agent_output=response, channel="demo")
            )
            n_interactions += 1
            s = soul.state
            print(dim(f"\n  [Observed: mood={s.mood.value}, energy={s.energy:.0f}]"))

            # 5. Auto-reflect every 5 interactions
            if n_interactions % 5 == 0:
                print(dim("  [Auto-reflecting...]"))
                r = await soul.reflect()
                if r and r.themes:
                    print(dim(f"  [Reflection themes: {', '.join(r.themes[:3])}]"))
            print()

    except KeyboardInterrupt:
        print(col("\n\n  Interrupted.", YELLOW))

    # -- Graceful exit: export .soul file
    print(dim("\n  Saving soul..."))
    try:
        await soul.export(soul_file)
        print(col(f"  Exported to {soul_file}", GREEN))
    except Exception as e:
        print(col(f"  Export failed: {e}", RED))

    s, stats = soul.state, mem_stats(soul)
    print(
        f"  Session: {n_interactions} interactions, mood={s.mood.value}, "
        f"energy={s.energy:.0f}%, {sum(stats.values())} memories\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
