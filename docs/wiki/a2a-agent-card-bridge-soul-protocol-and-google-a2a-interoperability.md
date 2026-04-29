---
{
  "title": "A2A Agent Card Bridge: Soul Protocol and Google A2A Interoperability",
  "summary": "Provides bidirectional conversion between Soul Protocol souls and Google's A2A Agent Card JSON format, mapping soul identity, OCEAN personality traits, and skills in both directions. A stateless utility class with three static methods covering export, import, and non-destructive enrichment.",
  "concepts": [
    "A2A Agent Card",
    "OCEAN personality",
    "soul export",
    "soul import",
    "protocol bridge",
    "DID",
    "SoulExtension",
    "deepcopy",
    "skills mapping",
    "bidirectional conversion",
    "Google A2A"
  ],
  "categories": [
    "bridges",
    "interoperability",
    "identity",
    "integration"
  ],
  "source_docs": [
    "3681f24660ca3ea3"
  ],
  "backlinks": null,
  "word_count": 414,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Google's A2A (Agent-to-Agent) protocol uses "Agent Cards" — JSON documents that describe an agent's identity, capabilities, and endpoint. `A2AAgentCardBridge` lets soul-powered agents participate in A2A ecosystems by converting between the two formats without losing information on either side.

## Three Conversion Modes

### 1. Soul to Agent Card (`soul_to_agent_card`)

Converts a live `Soul` instance into a complete A2A Agent Card dict:

- **Identity**: Soul `name` and `archetype` map to Agent Card `name` and `description`.
- **Personality**: All five OCEAN traits (`openness`, `conscientiousness`, `extraversion`, `agreeableness`, `neuroticism`) are embedded in `extensions.soul.personality`.
- **Skills**: Each soul skill becomes an `A2ASkill` with `id`, `name`, and a generated description showing level and XP.
- **Soul Extension**: A `SoulExtension` block records the soul's DID, personality, version, and protocol identifier (`dsp/1.0`).

### 2. Agent Card to Soul (`agent_card_to_soul`)

Reconstitutes a `Soul` from an A2A Agent Card:

```python
# Extract personality from extensions.soul if present
personality = Personality(**personality_kwargs)

# Prefer DID from soul extension; generate one if missing
did = soul_ext_data.get("did", "") or generate_did(card.name)

# Build identity, core memory, config, then construct Soul
soul = Soul(config)
```

This path uses synchronous `Soul(config)` construction (not `await Soul.birth()`) because it runs in a context that may not have an event loop. The trade-off is that the soul skips the async initialization pipeline (no engine wiring, no first reflection).

### 3. Enrich Agent Card (`enrich_agent_card`)

Adds soul metadata to an existing Agent Card without modifying the input:

```python
enriched = copy.deepcopy(card)
enriched["extensions"]["soul"] = soul_ext.model_dump()
return enriched
```

`copy.deepcopy` ensures the original dict is not mutated — critical when the caller holds references to the original card or passes it to multiple recipients.

## Data Mapping

| Soul Protocol | A2A Agent Card |
|---|---|
| `identity.name` | `name` |
| `identity.archetype` | `description` |
| `identity.did` | `extensions.soul.did` |
| `dna.personality.*` | `extensions.soul.personality.*` |
| `skills.skills[*]` | `skills[*]` |
| `_config.version` | `version` |

## Import Handling

The `agent_card_to_soul` method uses a local import for `Soul` and `generate_did` to avoid circular imports at module load time:

```python
from soul_protocol.runtime.identity.did import generate_did
from soul_protocol.runtime.soul import Soul
```

## Known Gaps

- `agent_card_to_soul` uses synchronous soul construction, bypassing the `Soul.birth()` async pipeline. The resulting soul has no cognitive engine, no initial state, and no first reflection.
- Skills round-trip lossily: description is generated as `"Level N skill (X XP)"` rather than preserving the original skill description from the source soul.
- No validation that `card.version` is a valid semver string before passing it to `SoulConfig`.