---
{
  "title": "Simulated Agent and User Profile Generator for Research Experiments",
  "summary": "Generates 1,000 diverse simulated agent profiles with realistic OCEAN personality distributions and 1,000 matched user profiles for a specified use case domain, used as the participant pool for Soul Protocol's validation experiments. All sampling uses a seeded RNG to guarantee reproducible results across experiment runs.",
  "concepts": [
    "OCEAN personality model",
    "AgentProfile",
    "UserProfile",
    "truncated normal distribution",
    "seeded RNG",
    "archetype pool",
    "value pool",
    "communication style",
    "personality-to-behavior mapping",
    "topic pools",
    "generate_agents",
    "generate_users",
    "behavioral tendencies",
    "simulation population"
  ],
  "categories": [
    "research",
    "simulation",
    "personality-modeling",
    "soul-protocol"
  ],
  "source_docs": [
    "ac73dba3539d3835"
  ],
  "backlinks": null,
  "word_count": 535,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`agents.py` creates the synthetic participants for the 20,000-run validation study. It must balance two competing demands: diversity (so results generalize across personality types) and reproducibility (so the same 1,000 agents are generated every run, making results comparable across conditions).

## OCEAN Profile Generation

Each agent's personality is represented as five float values between 0.05 and 0.95 using a truncated normal distribution:

```python
def _truncated_normal(mean: float, std: float, rng: random.Random) -> float:
    """Sample from normal distribution, clamped to [0.05, 0.95]."""
    return _clamp(rng.gauss(mean, std), 0.05, 0.95)
```

The truncation bounds (0.05, 0.95) prevent extreme personality values that have no real-world analog. With default parameters (`ocean_mean=0.5`, `ocean_std=0.15`), most agents cluster between 0.2 and 0.8 — the realistic human range. Using `rng.gauss` on a seeded `random.Random` instance (not the global `random.gauss`) prevents external code from corrupting the distribution by consuming random state.

## Communication Style Derived from OCEAN

Rather than randomly assigning communication style, the code derives it from OCEAN traits:

```python
warmth_idx = min(2, int(ocean["agreeableness"] * 3))     # high agreeableness → warm
verbosity_idx = min(4, int(ocean["extraversion"] * 5))   # high extraversion → verbose
formality_idx = min(2, int((1 - ocean["openness"]) * 3)) # low openness → formal
```

This mapping makes agent behavior psychologically coherent — a highly agreeable agent will use warm language; a highly extraverted one will be more verbose. Without this coupling, communication style and OCEAN traits would be independent, making agents unrealistic.

## Behavioral Tendency Derivation

`AgentProfile.__post_init__` computes three behavioral tendency fields directly from OCEAN:

```python
self.emotional_reactivity = self.ocean["neuroticism"]
self.detail_orientation = self.ocean["conscientiousness"]
self.social_energy = self.ocean["extraversion"]
```

These are convenience aliases used by the conditions layer when simulating how an agent responds to emotionally charged or detail-heavy interactions.

## Agent Pool Diversity

20 archetypes and 20 values are drawn from curated pools:

```python
archetype = rng.choice(ARCHETYPES)        # e.g., "The Deep Listener"
values = rng.sample(VALUE_POOL, k=rng.randint(2, 4))  # 2-4 values per agent
```

The pool sizes ensure meaningful variety — 20 archetypes * varying value combinations produce effectively unique agents. The persona string is auto-generated from the selected archetype and values:

```python
persona = f"I am {name}, {archetype.lower()}. I value {', '.join(values[:-1])} and {values[-1]}."
```

## User Profile Generation

`generate_users()` creates a matched pool of simulated users per use case domain. Topic pools are domain-specific:

| Use Case | Topic Examples |
|---|---|
| `support` | billing, refund, account, shipping |
| `coding` | python, SQL, debugging, architecture |
| `companion` | mood, goals, hobbies, travel |
| `knowledge` | research, writing, strategy, data |

`UserProfile.consistency` (0.3–0.9) controls how often the simulated user revisits previous topics — high consistency users test cross-session recall; low consistency users test topic-switching behavior.

`UserProfile.sentiment_bias` is sampled from a Gaussian centered at 0.2 with std 0.3 — slightly positive, reflecting typical user sentiment distributions rather than neutral.

## Known Gaps

- The agent persona template (`"I am Agent-0000, the helpful guide..."`) is simplistic. Real agents would have richer backstory text that influences the soul's extraction pipeline differently for each agent. The current template may produce homogeneous extraction behavior despite diverse OCEAN profiles.
- No validation that generated OCEAN values actually produce meaningfully different behavior in the Soul Protocol runtime — the distribution is statistically correct but functional validity is untested.