---
{
  "title": "Protocol Bridges Package: A2A Interoperability",
  "summary": "Package init for the runtime bridges subsystem, currently exposing the `A2AAgentCardBridge` for bidirectional conversion between Soul Protocol and Google's A2A Agent Card format. Bridges enable soul-powered agents to participate in multi-agent ecosystems that use other protocols.",
  "concepts": [
    "A2A",
    "Agent Card",
    "protocol bridge",
    "interoperability",
    "OCEAN personality",
    "Google A2A",
    "adapter pattern",
    "bridges package",
    "multi-agent",
    "soul export"
  ],
  "categories": [
    "runtime",
    "bridges",
    "interoperability",
    "integration"
  ],
  "source_docs": [
    "5fc60f7570f45e2f"
  ],
  "backlinks": null,
  "word_count": 330,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `bridges` package provides protocol adapters that allow Soul Protocol to interoperate with external agent protocols. Instead of requiring every ecosystem to speak Soul Protocol natively, bridges convert between formats — letting soul-powered agents participate in any network that understands the target protocol.

## Current Exports

```python
from .a2a import A2AAgentCardBridge

__all__ = ["A2AAgentCardBridge"]
```

The single current bridge is `A2AAgentCardBridge`, added in March 2026 to support Google's Agent-to-Agent (A2A) protocol.

## Design Rationale

Keeping bridges in a dedicated subpackage has several advantages:

1. **Optional dependencies**: Each bridge may require different third-party packages. The `bridges/` namespace signals to callers that these are adapters — not core functionality — and may have install requirements.
2. **Protocol isolation**: Bridge code imports from `soul_protocol.spec.a2a` (the protocol spec) and `soul_protocol.runtime.types` (the runtime models). It does not import from the broader runtime engine, keeping the dependency graph shallow.
3. **Extensibility**: Adding a new bridge (e.g., for MCP, OpenAI function-calling schemas, or LangChain tool formats) means adding a new module to this package and re-exporting from `__init__.py` — no changes to core runtime code.

## A2A Bridge

`A2AAgentCardBridge` is a stateless converter. All methods are static:

- `soul_to_agent_card(soul, url)` — Converts a `Soul` instance to an A2A Agent Card dict, embedding OCEAN personality traits and skills in the `extensions.soul` block.
- `agent_card_to_soul(card)` — Reconstructs a `Soul` from an A2A Agent Card, extracting identity, personality, and skills.
- `enrich_agent_card(card, soul)` — Non-destructively adds soul metadata to an existing Agent Card without clobbering other extensions.

## Integration Pattern

```python
from soul_protocol.runtime.bridges import A2AAgentCardBridge

# Export a soul as an A2A Agent Card
card = A2AAgentCardBridge.soul_to_agent_card(soul, url="https://agent.example.com/")

# Import a soul from an A2A Agent Card
soul = A2AAgentCardBridge.agent_card_to_soul(card)
```

## Known Gaps

- Only one bridge exists. MCP, LangChain, OpenAI tool schema, and other ecosystem bridges are not yet implemented.
- The A2A bridge performs synchronous soul construction (`Soul(config)`) rather than the async `Soul.birth()` path, which means the soul starts without running the full initialization pipeline.