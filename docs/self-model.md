<!-- Covers: Self-model architecture, emergent domain discovery, Klein's self-concept,
     seed domains, keyword growth, serialization, and prompt generation. -->

# Self-Model (Klein's Self-Concept)

The soul builds a model of who it is by observing what it does. This is not programmed — it emerges from accumulated experience.

Based on Stanley Klein's theory of self-knowledge: self-concept is not a single thing but a collection of domain-specific self-images, each with a confidence level built from evidence.


## How It Works

Every time `soul.observe()` runs, the self-model scans the interaction for patterns. If the soul keeps helping with Python code, it develops a "technical_helper" self-image with growing confidence. If it starts helping with cooking, a "cooking" domain emerges automatically.

```python
soul = await Soul.birth(name="Chef", archetype="Kitchen Companion")

# After many cooking interactions...
await soul.observe(Interaction(
    user_input="How do I make sourdough bread?",
    agent_output="Start with a strong starter...",
))

# The soul develops a cooking-related self-image
images = soul.self_model.get_active_self_images()
# [SelfImage(domain="sourdough_bread", confidence=0.18, evidence_count=2)]
```


## Emergent Domain Discovery

The soul is not limited to predefined categories. Domains are discovered from interaction content:

1. **Extract meaningful keywords** — Filter out stop words, keep domain-specific terms
2. **Match against existing domains** — Each domain tracks keywords from past interactions
3. **Reinforce or create** — If keywords match an existing domain (2+ overlaps), reinforce it. Otherwise, create a new domain from the most prominent keywords.

Domain names are auto-generated from content. A soul that helps with "recipe", "ingredients", "bake" creates a domain like `"ingredients_recipe"`. Over time, the domain's keyword vocabulary expands as the soul encounters more related content.

### No Predefined Limits

A soul can develop any number of domains:

```
technical_helper  (confidence: 0.87, 142 interactions)
cooking           (confidence: 0.65, 38 interactions)
fitness_guide     (confidence: 0.43, 15 interactions)
travel_planning   (confidence: 0.22, 5 interactions)
```

The top domains by confidence feed into the system prompt via `to_system_prompt()`, giving the soul self-awareness about its strongest roles.


## Default Seed Domains

New souls start with six seed domains that cover common use cases:

| Domain | Example Keywords |
|--------|-----------------|
| `technical_helper` | python, code, debug, api, docker |
| `creative_writer` | write, story, poem, blog, essay |
| `knowledge_guide` | explain, teach, learn, research, science |
| `problem_solver` | solve, fix, issue, troubleshoot, diagnose |
| `creative_collaborator` | brainstorm, design, prototype, iterate |
| `emotional_companion` | feel, support, listen, comfort, empathy |

These seeds bootstrap domain detection before the soul has enough experience to discover domains on its own. They are not a ceiling — the soul can and will create new domains beyond these six.

### Custom Seed Domains

Override the defaults to match your use case:

```python
soul = await Soul.birth(
    name="ChefBot",
    seed_domains={
        "cooking": ["recipe", "ingredients", "bake", "cook", "kitchen"],
        "nutrition": ["calories", "protein", "vitamins", "diet", "healthy"],
    },
)
```

Or start with a blank slate (all domains are emergent):

```python
from soul_protocol.memory.self_model import SelfModelManager

manager = SelfModelManager(seed_domains={})
```


## Confidence Formula

Confidence grows with evidence using a diminishing returns curve:

```
confidence = min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence_count * 0.1)))
```

| Evidence Count | Confidence | Label |
|---------------|-----------|-------|
| 1 | 0.18 | emerging |
| 5 | 0.36 | emerging |
| 10 | 0.52 | growing |
| 25 | 0.71 | high |
| 50 | 0.82 | high |
| 100+ | 0.90+ | high |

The soul becomes more certain over time but never fully certain (capped at 0.95). This matches human self-knowledge — you know you're good at something, but there's always room for growth.


## Keyword Growth

Domain vocabularies are not static. Each time a domain is reinforced, the new meaningful keywords from that interaction are added to its vocabulary:

```
Interaction 1: "Help me debug my Python function"
  → technical_helper gets: {python, debug, function}

Interaction 15: "Review this FastAPI endpoint"
  → technical_helper gets: {python, debug, function, ..., fastapi, endpoint, review}
```

This means the domain gets better at matching related content over time. A mature "technical_helper" domain recognizes far more technical terms than a fresh one.


## Serialization

The self-model persists across save/load, including learned domain keywords:

```json
{
  "self_images": {
    "technical_helper": {
      "domain": "technical_helper",
      "confidence": 0.82,
      "evidence_count": 47
    },
    "cooking": {
      "domain": "cooking",
      "confidence": 0.43,
      "evidence_count": 12
    }
  },
  "domain_keywords": {
    "technical_helper": ["algorithm", "api", "class", "code", "debug", "python", ...],
    "cooking": ["bake", "cook", "ingredients", "recipe", "sourdough", ...]
  },
  "relationship_notes": {
    "user": "Name: Prakash; Works at: Qbtrix"
  }
}
```


## In the System Prompt

The top self-images are included in `soul.to_system_prompt()`:

```markdown
## Self-Understanding

- technical helper (high confidence, 47 supporting interactions)
- cooking (growing confidence, 12 supporting interactions)
```

This gives the soul awareness of its own strengths, which naturally influences how it responds.


## Relationship Notes

Beyond self-images, the self-model also tracks relationship notes — facts about key people and entities the soul interacts with. These are extracted from semantic facts:

- "User's name is Prakash" → `relationship_notes["user"] = "Name: Prakash"`
- "User works at Qbtrix" → `relationship_notes["user"] = "Name: Prakash; Works at: Qbtrix"`

When a `CognitiveEngine` is provided, the LLM extracts richer relationship notes from interactions.
