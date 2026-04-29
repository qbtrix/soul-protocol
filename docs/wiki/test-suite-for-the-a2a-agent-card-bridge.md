---
{
  "title": "Test Suite for the A2A Agent Card Bridge",
  "summary": "This test suite validates bidirectional conversion between Soul Protocol souls and Google A2A Agent Cards via `A2AAgentCardBridge`. It covers spec model serialization, full round-trip identity preservation (name, DID, OCEAN traits, skills), immutability guards on enrichment, and file-based CLI round-trips.",
  "concepts": [
    "A2A Agent Card",
    "A2AAgentCardBridge",
    "soul conversion",
    "round-trip identity",
    "OCEAN traits",
    "DID preservation",
    "SoulExtension",
    "immutability",
    "multi-agent interop"
  ],
  "categories": [
    "testing",
    "a2a",
    "interoperability",
    "test"
  ],
  "source_docs": [
    "b09f22f85525eabf"
  ],
  "backlinks": null,
  "word_count": 504,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Agent-to-Agent (A2A) is Google's open standard for inter-agent communication. A soul needs to present itself as an A2A Agent Card to participate in multi-agent systems. The bridge translates in both directions:

- `soul_to_agent_card()` — export a soul as a JSON-serializable Agent Card dict
- `agent_card_to_soul()` — import an Agent Card and construct a Soul from it
- `enrich_agent_card()` — add soul metadata to an existing card without mutating the original

The test suite was introduced alongside the bridge (2026-03-23) and covers 30+ scenarios.

## Spec Model Tests (`TestA2ASpecModels`)

Verifies that the three Pydantic models (`A2ASkill`, `SoulExtension`, `A2AAgentCard`) serialize and deserialize correctly:

- Default values are as documented (`protocol == "dsp/1.0"`, `personality == {}`, `did == ""`)
- A full round-trip through `model_dump()` and reconstruction preserves all fields
- Optional nested structures (skills, extensions) default to empty collections

## Soul → Card Conversion (`TestSoulToAgentCard`)

Key contracts locked by this class:

```python
card = A2AAgentCardBridge.soul_to_agent_card(soul, url="https://soul.dev")
# card["extensions"]["soul"]["protocol"] == "dsp/1.0"
# card["extensions"]["soul"]["did"] == soul.did
# card["extensions"]["soul"]["personality"] == {"openness": 0.9, ...}
# card["provider"]["organization"] == "Soul Protocol"
# card["version"] == "1.0.0"
```

Skill descriptions include the level (`"Level 3"`) so consumers can assess capability depth without parsing the extension payload.

An empty soul (no skills, default personality) still produces a valid card — important for onboarding flows where a soul is instantiated before any skills are assigned.

## Card → Soul Conversion (`TestAgentCardToSoul`)

This direction is more defensive. Tests verify:

- Missing name raises an exception (a nameless soul cannot be created)
- Missing soul extension still works — defaults to `openness=0.5` for all OCEAN traits
- Empty extensions dict works
- A `A2AAgentCard` model can be passed directly (not just a raw dict)
- Skills in the card become `Skill` objects in `soul.skills`
- Description maps to `core_memory.persona`

## Immutability Guard (`TestEnrichAgentCard`)

The `enrich_agent_card()` method must not mutate its input dict. The test explicitly checks this:

```python
card = {"name": "Original", "extensions": {"other": True}}
enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
assert "soul" not in card["extensions"]   # original unchanged
assert "soul" in enriched["extensions"]   # enriched has it
```

This prevents a class of subtle bug where the caller's reference to the card is silently modified.

## Round-Trip Identity Preservation (`TestRoundTrip`)

The round-trip suite verifies that `soul → card → soul` is lossless for all five OCEAN traits, DID, name, archetype, and skills:

```python
original → card = soul_to_agent_card(original)
restored = agent_card_to_soul(card)
assert restored.dna.personality.openness == original.dna.personality.openness
assert restored.did == original.did
```

## CLI Integration (`TestCLICommands`)

End-to-end tests exercise the file-based workflow: exporting a soul to a JSON card file and re-importing it. This validates that the JSON serialization (using `default=str` for non-serializable types) round-trips correctly through `json.dumps` / `json.loads`.

## Known Gaps

- Tests do not cover partial OCEAN updates (only some traits in the extension). The behavior when some traits are present and others are absent relies on default values of `0.5` — this is correct but not explicitly pinned.
- Memory contents are not part of the A2A round-trip; only `core_memory.persona` is reconstructed from the card description.