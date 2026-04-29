---
{
  "title": "Simulate Script: Comprehensive Soul Protocol Scenario Test Suite",
  "summary": "A standalone simulation script containing 30+ named scenarios that test every surface of the soul-protocol API — from basic lifecycle and memory recall to adversarial inputs, concurrent async safety, cross-platform migration, evolution system, knowledge graph, and graceful degradation. Each scenario is independently runnable and produces a detailed Rich-formatted report.",
  "concepts": [
    "simulate",
    "scenario catalog",
    "adversarial testing",
    "concurrent async",
    "platform migration",
    "evolution system",
    "knowledge graph",
    "ACT-R decay",
    "personality stability",
    "memory pressure",
    "config roundtrip",
    "Check pattern",
    "ScenarioResult",
    "soul lifecycle"
  ],
  "categories": [
    "scripts",
    "simulation",
    "functional-testing",
    "soul-protocol"
  ],
  "source_docs": [
    "c7adeac534bc3e01"
  ],
  "backlinks": null,
  "word_count": 443,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`simulate.py` is the broadest functional test surface for soul-protocol. While `e2e_paw_integration.py` validates the PocketPaw-specific integration path and the research framework validates recall metrics statistically, this script validates the full API surface for correctness and robustness. It is the first thing to run when validating a new soul-protocol version or investigating a regression.

## Scenario Catalog

The 30+ scenarios are organized by concern:

**Correctness scenarios:**
- `scenario_coding_assistant` — 40 coding interactions, first-person fact injection
- `scenario_multi_domain` — coding, cooking, fitness, travel, music
- `scenario_companion` — warm companion soul, emotional conversations
- `scenario_novel_domain_discovery` — no seed domains, learns from scratch
- `scenario_recall_quality` — plant specific facts, query, measure precision

**Scale and performance:**
- `scenario_stress_test` — 200+ interactions, mixed domains
- `scenario_memory_pressure` — 800+ interactions, test store limits
- `scenario_growth_curve` — metric milestones verifying sub-linear memory scaling

**Configuration surface:**
- `scenario_minimal_config` — just a name, all defaults
- `scenario_maximal_config` — every parameter specified
- `scenario_config_roundtrip` — YAML birth → export → awaken, verify survival
- `scenario_config_file_formats` — YAML and JSON birth

**Identity and personality:**
- `scenario_personality_stability` — DNA immutable across 500 one-sided interactions
- `scenario_opposite_personalities` — two souls with opposite OCEAN, identical inputs
- `scenario_dynamic_personality_expression` — 3 differently configured souls, same 20 interactions

**Robustness:**
- `scenario_adversarial` — empty inputs, huge messages, gibberish, injection attempts
- `scenario_degradation` — corrupted/invalid inputs to `awaken()`
- `scenario_concurrent` — 20 concurrent `observe()` calls via `asyncio.gather()`

**Advanced features:**
- `scenario_evolution` — propose, approve, reject mutations, immutable guard, disabled mode
- `scenario_emotional` — energy drain, mood transitions, manual `feel()`, rest recovery
- `scenario_graph` — entity extraction, relationship tracking, export/import
- `scenario_forgetting` — ACT-R decay: recency and frequency ranking
- `scenario_migration` — Discord → Slack platform migration

## Check Pattern

Each scenario uses a `Check` dataclass and collects results into `ScenarioResult`:

```python
@dataclass
class Check:
    description: str
    expected: Any
    actual: Any
    passed: bool
```

Checks are explicit assertions with both expected and actual values captured, making failures self-diagnosing without needing to re-run in a debugger.

## Diagnostic Utilities

```python
def count_semantic(soul) -> int:   # direct store access, not via recall()
def count_episodic(soul) -> int:
def count_total_memories(soul) -> int:
def get_self_images_full(soul) -> dict:
```

These bypass the recall API to directly inspect internal state. This is intentional: `recall()` filters by relevance, which makes it unsuitable for verifying that the *right number* of memories were stored. Direct store counts provide ground truth.

## Known Gaps

- Scenarios are defined as top-level async functions with no shared setup. Duplicated soul birth code across 30 scenarios means a soul API change requires 30 edits.
- No scenario currently tests `soul.bond()` interactions across multiple users within a single soul — multi-user bonding is a known untested surface.
