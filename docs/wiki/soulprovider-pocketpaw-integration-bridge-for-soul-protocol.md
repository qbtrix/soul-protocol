---
{
  "title": "SoulProvider: PocketPaw Integration Bridge for Soul Protocol",
  "summary": "Defines `SoulProvider`, a reference integration class that replaces PocketPaw's `DefaultBootstrapProvider` with a soul-driven system prompt generator, interaction tracker, and auto-save mechanism. It bridges soul-protocol's memory and identity system into any agent loop that calls a `get_system_prompt()` / `on_interaction()` pattern, with zero dependency on PocketPaw internals.",
  "concepts": [
    "SoulProvider",
    "DefaultBootstrapProvider",
    "PocketPaw integration",
    "system prompt",
    "memory recall",
    "agent loop",
    "Soul.awaken",
    "Soul.birth",
    "auto-save",
    "on_interaction",
    "get_system_prompt",
    "low energy adaptation",
    "soul state",
    "provider pattern"
  ],
  "categories": [
    "integration",
    "examples",
    "agent-loop",
    "soul-protocol"
  ],
  "source_docs": [
    "c1224d58871eb953"
  ],
  "backlinks": null,
  "word_count": 603,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`pocketpaw_integration.py` exists because soul-protocol is a standalone SDK, but its value only becomes apparent when wired into a real agent loop. PocketPaw's `DefaultBootstrapProvider` generates static system prompts — the same string every turn. `SoulProvider` replaces that with a prompt that changes based on what the soul remembers about the current user.

The module is deliberately self-contained (`zero PocketPaw dependencies`) so it can be used as a reference pattern for any agent framework that follows the provider/bootstrap pattern.

## Architecture

`SoulProvider` wraps a `Soul` instance and exposes three primary async methods:

| Method | Purpose |
|---|---|
| `get_system_prompt(user_query, sender_id)` | Builds the system prompt for each turn |
| `on_interaction(user_input, agent_output, channel, metadata)` | Called after each exchange |
| `save()` | Persists the soul to disk |

Two factory class methods handle construction:
- `SoulProvider.from_file(path)` — awakens an existing `.soul` file
- `SoulProvider.from_name(name, archetype)` — births a new soul by name

## System Prompt Assembly

The prompt is built in three layers on every call:

```python
# 1. Base: DNA + identity + core memory + state
prompt = self._soul.to_system_prompt()

# 2. Relevant memories injected if user_query is provided
if user_query:
    memories = await self._soul.recall(user_query, limit=self._recall_limit)
    if memories:
        prompt += "\n\n## Relevant Memories\n"
        for mem in memories:
            prefix = f"[{mem.type.value}]" if mem.type else ""
            prompt += f"- {prefix} {mem.content}\n"

# 3. State-aware annotation for low energy
if state.energy < 30:
    prompt += "\n\n*Note: You're feeling low on energy...*\n"
```

This layered approach separates concerns cleanly: the base prompt handles static identity, the memory block provides dynamic episodic context, and the state annotation handles behavioral adaptation. Each layer is independently optional — if no query is provided, no memories are injected; if energy is fine, no annotation is appended.

## Why Memory Recall is Query-Anchored

Recalling all memories every turn would inject irrelevant context, consuming tokens and reducing response relevance. Anchoring recall to `user_query` means only memories semantically related to the current topic appear in the prompt — the soul "thinks" about what the user said before replying, mirroring how human memory works.

## Auto-Save Pattern

```python
self._interaction_count += 1
if self._interaction_count % self._auto_save_interval == 0:
    await self.save()
```

Every N interactions (default 10), the soul is saved automatically. This prevents data loss if the process is killed between explicit save calls. The interval is configurable at construction time — high-throughput applications might increase it to reduce I/O; high-stakes companion applications might reduce it to 1 (save every interaction).

## Low-Energy State Adaptation

The energy check (`state.energy < 30`) demonstrates behavioral adaptation without modifying the LLM's weights — the soul's state changes the instructions it runs under. An agent with low energy will have "Keep responses concise" injected, naturally producing shorter replies without any code changes to the LLM call site.

## `get_soul_status()` for Dashboards

Returns a dict suitable for display in a monitoring dashboard: soul name, DID, mood, energy, memory count, and bond strength. This is important for operational visibility — operators should be able to inspect a running soul's state without accessing its internals directly.

## Known Gaps

- `sender_id` is accepted as a parameter but the current implementation does not use it to partition memories per sender. Multi-user channels (e.g., a Discord server where multiple users talk to the same bot) would need additional logic to scope recall by sender.
- The auto-save writes the entire soul on every N-th interaction rather than a delta. For souls with large memory stores this may become a bottleneck.
- No error handling around `self._soul.observe()` — if observation fails (e.g., LLM extraction times out), the exception propagates to the caller uncaught.