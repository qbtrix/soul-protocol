---
{
  "title": "Real-World End-to-End Test Suite — Developer Onboarding, Bonding, and Evolution Scenarios",
  "summary": "Scenario-driven end-to-end tests that simulate realistic human-soul conversations across multiple contexts: developer technical discussions, personal emotional bonding, and mixed sessions. Tests validate that all soul systems (entity extraction, knowledge graph, bond growth, evolution, self-model) fire correctly in natural usage patterns.",
  "concepts": [
    "scenario-based testing",
    "entity extraction",
    "knowledge graph",
    "bond growth",
    "evolution triggers",
    "self-model",
    "bond-memory visibility",
    "private memories",
    "personality evolution",
    "emotional interactions",
    "high-quality streak"
  ],
  "categories": [
    "testing",
    "integration",
    "real-world-scenarios",
    "test"
  ],
  "source_docs": [
    "2759fa1a8e2756dd"
  ],
  "backlinks": null,
  "word_count": 396,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Unlike integration tests that call soul methods directly, this suite simulates actual conversation flows and validates emergent behavior. It answers the question: when a real user talks to a soul, do all the systems activate as expected?

## Why This Exists

Unit and integration tests can all pass while the system fails in practice if the wiring between components is wrong. This suite validates the full observable pipeline — entity extraction feeds the knowledge graph, which feeds the self-model, which influences context — using natural language inputs.

## Developer Onboarding Scenario

`TestDeveloperOnboarding` simulates a developer introducing themselves and discussing technology:

```python
# Interactions mention Python, Rust, AI frameworks
async def test_entities_extracted(interactions)
async def test_skills_learned_from_entities(interactions)
async def test_knowledge_graph_has_nodes(interactions)
async def test_bond_strengthens(interactions)
```

The `interactions()` fixture generates a realistic conversation batch. Tests confirm that topic entities (programming languages, tools) are extracted, knowledge graph nodes are created, and skills are inferred — all from natural speech without explicit annotations.

## Personal Bonding Scenario

`TestPersonalBonding` simulates emotional/personal conversations:

```python
async def test_bond_grows_with_emotional_interactions(interactions)
async def test_people_extracted_from_conversation(interactions)
async def test_memories_stored_from_personal_convo(interactions)
```

Emotional interactions should strengthen the bond more than technical ones. The test validates that personal disclosures are stored as episodic memories and that named people mentioned in conversation are extracted as entities.

## Evolution Triggers

`TestEvolutionTriggers` validates the evolution system's threshold logic:

```python
async def test_evolution_triggers_after_streak()
```

Evolution requires 5+ high-quality interactions in a streak. This test ensures the threshold is respected — evolution should not trigger prematurely (which would create unstable personality drift) or fail to trigger when earned.

## Bond-Memory Visibility

`TestBondMemoryVisibility` verifies that bond strength gates memory access:

```python
async def test_low_bond_hides_private_memories()
async def test_context_for_prompt_uses_bond()
```

Private memories (high sensitivity) should not appear in the system prompt for low-bond sessions. This is a privacy and trust mechanism — the soul reveals more as the relationship deepens.

## Mixed Conversation

`TestMixedConversation.test_all_systems_fire_in_realistic_session()` is the most comprehensive single test: it runs a combined technical + personal + project conversation and verifies that entity extraction, knowledge graph, bond, evaluation history, and self-model all produce non-empty results.

## Evolution Persistence

`TestEvolutionFires` verifies that evolution mutations persist through export/awaken — ensuring that personality changes earned through interaction are not lost on the next session.

## Known Gaps

Tests use fixture-generated interactions rather than truly random inputs. Edge cases involving ambiguous entity types (is "Python" the language or the snake?) are not covered.