---
{
  "title": "A2A Agent Card Models: Soul Protocol Interop with Google's Agent-to-Agent Protocol",
  "summary": "`spec/a2a.py` provides Pydantic models that map Google's A2A Agent Card specification to Soul Protocol primitives. `A2AAgentCard` is the agent's public identity, `A2ASkill` advertises capabilities, and `SoulExtension` embeds a soul's DID and OCEAN personality into the card's extension block.",
  "concepts": [
    "A2AAgentCard",
    "A2ASkill",
    "SoulExtension",
    "Agent Card",
    "A2A protocol",
    "agent interop",
    "DID",
    "OCEAN",
    "DSP",
    "extensions block",
    "Google A2A"
  ],
  "categories": [
    "spec",
    "interoperability",
    "agent protocol"
  ],
  "source_docs": [
    "d145cadfd9b0fbb7"
  ],
  "backlinks": null,
  "word_count": 460,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The A2A (Agent-to-Agent) protocol, developed by Google, defines a standard JSON schema for agents to advertise their identity, capabilities, and skills. `spec/a2a.py` makes Soul Protocol agents first-class A2A participants by providing three Pydantic models that serialize to/from A2A-compliant JSON: `A2ASkill`, `SoulExtension`, and `A2AAgentCard`.

## Why This Exists

Without A2A interop, Soul Protocol agents are isolated — discoverable only through bespoke integrations. By conforming to the A2A Agent Card spec, any A2A-compatible discovery service, orchestrator, or tool-use framework can find and invoke soul-powered agents without custom glue code.

The `SoulExtension` block specifically solves the problem of communicating soul identity across agent boundaries. When one agent calls another, it can inspect the target's `extensions.soul` block to know whether the target has persistent memory, what personality profile it carries, which DSP version it speaks, and what its DID is. This enables soul-aware routing: an orchestrator can prefer memory-capable agents for relationship tasks and stateless agents for one-shot queries.

## Models

### A2ASkill

A single skill entry in the Agent Card's `skills` array:

```python
A2ASkill(
    id="summarize",
    name="Text Summarizer",
    description="Summarizes long documents into bullet points.",
    tags=["nlp", "summarization"]
)
```

Skills are discovered by A2A orchestrators to route tasks to capable agents. The `tags` list enables semantic matching beyond the exact ID.

### SoulExtension

Embedded under `extensions.soul` to advertise persistent soul identity:

```python
SoulExtension(
    did="did:soul:aria-abc123",
    personality={"openness": 0.8, "conscientiousness": 0.7},
    soul_version="0.4.4",
    protocol="dsp/1.0",
)
```

The `protocol` field defaults to `"dsp/1.0"` (Digital Soul Protocol v1.0), enabling A2A consumers to gate on protocol version before attempting soul-specific interactions. A consumer that only supports `dsp/0.x` can reject `dsp/1.0` agents gracefully.

### A2AAgentCard

The full public identity of the agent:

```python
card = A2AAgentCard(
    name="Aria",
    description="A helpful assistant with persistent memory.",
    url="https://agents.example.com/aria",
    version="1.0",
    skills=[A2ASkill(id="chat", name="Conversational Chat")],
    extensions={"soul": soul_ext.model_dump()},
)
```

The `extensions` field is `dict[str, Any]` — deliberately schema-free — allowing Soul Protocol to evolve its extension block without breaking A2A parsers that do not understand the soul extension. Unknown extension keys are ignored by conformant A2A clients.

## Data Flow

```
Soul identity + OCEAN traits
  → SoulExtension(did, personality, soul_version)
  → A2AAgentCard.extensions["soul"] = soul_ext.model_dump()
  → card.model_dump_json()           # A2A-compliant JSON
  → published to A2A discovery endpoint
```

## Serialization Guarantee

Because all three models use Pydantic `BaseModel`, they serialize cleanly to JSON via `model_dump_json()` or `model_dump(mode="json")`. Nested `dict[str, Any]` fields (like `provider`, `capabilities`, `extensions`) pass through unchanged, preserving A2A-spec fields that Soul Protocol does not model.

## Known Gaps

- The `A2AAgentCard.capabilities` field is `dict[str, Any]` with no defined sub-schema. The A2A spec defines standard capability keys (`streaming`, `pushNotifications`, etc.) that are not yet modeled as typed fields.
- There is no helper function to build a complete `A2AAgentCard` from a `Soul` or `SoulConfig` instance — callers must manually map fields from the runtime types to these spec types.