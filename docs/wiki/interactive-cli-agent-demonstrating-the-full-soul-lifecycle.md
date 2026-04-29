---
{
  "title": "Interactive CLI Agent Demonstrating the Full Soul Lifecycle",
  "summary": "A runnable conversational agent that exercises the complete Soul Protocol lifecycle — birth, observe, recall, reflect, and save — with pluggable LLM backends (Claude, OpenAI, Ollama, and a no-LLM heuristic mode). It uses a dual-model architecture where a cheaper model handles soul cognition and a stronger model handles user-facing chat, demonstrating the cost-efficiency pattern Soul Protocol enables.",
  "concepts": [
    "interactive CLI",
    "soul lifecycle",
    "ClaudeEngine",
    "OpenAIEngine",
    "OllamaEngine",
    "HeuristicEngine",
    "dual-model architecture",
    "asyncio.to_thread",
    "REPL",
    "soul.observe",
    "soul.recall",
    "soul.reflect",
    "persistent sessions",
    "birth vs awaken"
  ],
  "categories": [
    "examples",
    "agent",
    "CLI",
    "soul-protocol"
  ],
  "source_docs": [
    "0946ba97980c4f55"
  ],
  "backlinks": null,
  "word_count": 577,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`real_agent.py` is the hands-on demonstration that a developer runs first when evaluating Soul Protocol. It is a complete, working conversational agent with a persistent soul — not a toy snippet. Its dual purpose is onboarding (show the full API surface) and validation (prove the lifecycle actually works end-to-end across multiple LLM providers).

## Engine Architecture

Four engine implementations all expose the same two-method interface:

```python
async def think(self, prompt: str) -> str: ...
async def chat(self, system: str, user_msg: str) -> str: ...
```

`think()` is used for internal soul cognition — extracting facts, scoring significance, generating reflections. `chat()` is used for user-facing responses. This split is deliberate: soul cognition runs on cheaper, faster models (Haiku, gpt-4o-mini) while the user sees output from stronger models (Sonnet, gpt-4o). The `HeuristicChatEngine` disables LLM calls entirely, using rule-based echo replies — this allows development and testing without API keys or credits.

### Engine Selection

```
--engine claude    → ClaudeEngine (haiku + sonnet)
--engine openai    → OpenAIEngine (gpt-4o-mini + gpt-4o)
--engine ollama    → OllamaEngine (single local model)
--engine heuristic → HeuristicChatEngine (no LLM, for testing)
```

The `build_engine(name)` factory validates the name against `ENGINE_LABELS` and raises clearly if an unknown engine is requested — a defensive pattern to surface CLI typos immediately.

## ANSI Color Helpers

The file implements a minimal ANSI escape code library inline, avoiding any terminal-formatting dependency:

```python
dim = lambda s: f"{DIM}{s}{RST}"
bold = lambda s: f"{BOLD}{s}{RST}"
col = lambda s, c: f"{c}{s}{RST}"
```

This is intentional — adding `rich` or `colorama` as a dependency for a demo script creates unnecessary friction when the script is copy-pasted into a new project.

## Soul Lifecycle Commands

The interactive REPL exposes soul commands as slash-prefixed input:

| Command | Function | Purpose |
|---|---|---|
| `/recall <query>` | `cmd_recall` | Search memories by query |
| `/state` | `cmd_state` | Show mood, energy, social battery |
| `/reflect` | `cmd_reflect` | Trigger soul self-reflection |
| `/memories` | `cmd_memories` | List all memories |
| `/save [path]` | `cmd_save` | Persist soul to disk |
| `/export [path]` | `cmd_export` | Export as portable .soul file |

These commands exist to make the soul's internal state inspectable during a live conversation. Without them, a developer cannot verify that observations are being extracted and stored correctly.

## Soul Loading Strategy

On startup, the agent either awakens an existing soul from a `--soul` path or births a new one with `--name`. The `--soul` path enables persistent sessions across multiple runs — restarting the agent and passing the same `.soul` file resumes the conversation with full memory intact.

## Async Thread Wrapping

All LLM calls use `asyncio.to_thread()` to run synchronous Anthropic/OpenAI SDK calls without blocking the event loop:

```python
async def think(self, prompt: str) -> str:
    return await asyncio.to_thread(self._call, self._think, prompt)
```

This is necessary because the Python SDKs for Anthropic and OpenAI expose synchronous HTTP calls, but `soul.observe()` is an async coroutine. Without `to_thread`, a single LLM call would block all concurrent soul operations.

## Known Gaps

- The Ollama engine uses a single model for both `think()` and `chat()`. A proper dual-model Ollama setup would use a smaller quantized model for cognition and a larger one for chat, but local model naming varies too much to hardcode.
- No graceful shutdown handler is shown — if the user hits Ctrl+C mid-conversation, the soul's unsaved observations are lost. A real deployment should catch `KeyboardInterrupt` and call `cmd_save()` before exit.