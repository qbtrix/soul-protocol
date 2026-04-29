---
{
  "title": "Research Scenario Bank: Multi-Turn Interaction Templates for Four Use Cases",
  "summary": "The scenario bank provides parameterized, multi-turn interaction sequences for four use cases — customer support, coding assistant, personal companion, and knowledge worker — each with embedded ground truth: planted facts, recall queries, emotional tone markers, and importance hints. Scenarios are personalized by `UserProfile` to increase coverage and ecological validity.",
  "concepts": [
    "Turn",
    "Scenario",
    "planted facts",
    "recall queries",
    "importance hint",
    "UserProfile",
    "customer support",
    "coding assistant",
    "companion",
    "knowledge worker",
    "significance gate",
    "ground truth"
  ],
  "categories": [
    "research",
    "scenarios",
    "evaluation",
    "soul-protocol"
  ],
  "source_docs": [
    "fe910817e7ce1257"
  ],
  "backlinks": null,
  "word_count": 392,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Testing memory recall with fabricated one-shot exchanges misses the core challenge: facts get buried under unrelated conversation, and recall must survive interference from subsequent turns. The scenario bank provides realistic multi-turn conversations that simulate how users actually interact with AI companions — sharing personal details casually, referencing earlier topics, expressing emotions over time.

## Data Model

```python
@dataclass
class Turn:
    user_input: str
    agent_output: str
    contains_fact: bool = False      # should this be stored?
    fact_content: str = ""           # what should be stored?
    references_previous: bool = False # does this reference earlier context?
    reference_topic: str = ""        # what earlier topic?
    expected_emotion: str = ""       # e.g. "frustrated", "happy"
    importance_hint: float = 0.5     # 0-1 significance hint

@dataclass
class Scenario:
    scenario_id: str
    use_case: str
    turns: list[Turn]
    planted_facts: list[str]           # deliberately planted for recall testing
    recall_queries: list[tuple[str, str]]  # (query, expected_fact) pairs
```

`importance_hint` serves as ground truth for significance filtering: a turn with `importance_hint=0.8` should be stored, one with `0.2` might be discarded. This enables precision/recall evaluation of the significance gate.

## Use Case Generators

| Generator | Scenarios | Themes |
|---|---|---|
| `_support_scenarios` | Account issues, loyalty info | Personal details, product usage |
| `_coding_scenarios` | Debugging, architecture | Technical facts, project context |
| `_companion_scenarios` | Emotional support, goals | Personal life, feelings |
| `_knowledge_scenarios` | Research, learning | Domain facts, cross-references |

Each generator is parameterized by `UserProfile` — the user's name, profession, and personality traits shape the scenario content, making each combination unique.

## Ground Truth Design

`planted_facts` are explicitly injected at known turn indices. `recall_queries` provide the test oracle: given query Q, the expected fact is F. This supports automated precision/recall measurement without LLM judges.

```python
recall_queries = [
    ("What is the user's name?", f"User's name is {user_name}"),
    ("What product does the user use?", f"User has been using {product}"),
]
```

## Known Gaps

- Scenario count per use case is fixed at a small number of templates. Parameterization by `UserProfile` produces variation but the structural patterns (turn 1: personal info, turn 4: loyalty info) are identical across users, which could cause the significance gate to overfit to position rather than content.
- `reference_topic` is a string label but is never validated against earlier `fact_content` values. A mismatch (e.g., referencing a topic that was never planted) would cause false negatives in recall evaluation.
