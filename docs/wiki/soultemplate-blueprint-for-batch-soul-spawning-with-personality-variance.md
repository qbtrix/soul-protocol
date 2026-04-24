---
{
  "title": "SoulTemplate — Blueprint for Batch Soul Spawning with Personality Variance",
  "summary": "`SoulTemplate` defines a reusable blueprint that a `SoulFactory` uses to spawn individual souls or batches with controlled personality variation. It carries a default personality (OCEAN traits as a dict), core memories to bootstrap, skill names, and variance settings for producing non-identical clones in batch operations.",
  "concepts": [
    "SoulTemplate",
    "personality_variance",
    "core_memories",
    "archetype",
    "batch spawning",
    "SoulFactory",
    "OCEAN traits",
    "name_prefix",
    "skills",
    "soul blueprint"
  ],
  "categories": [
    "identity",
    "spec layer",
    "soul creation",
    "templates"
  ],
  "source_docs": [
    "7275d2cb3ecccfe4"
  ],
  "backlinks": null,
  "word_count": 487,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Creating many souls manually — each with slightly different personalities, the same core memories, and the same skills — is tedious and error-prone. `SoulTemplate` solves this by encoding the common blueprint once so a `SoulFactory` can stamp out any number of souls from it, optionally adding random variance to produce distinct individuals rather than clones.

This is especially useful for agent swarms, evaluation harnesses (where you want multiple souls with controlled trait distributions), and bundled archetypes (where a product ships with a default personality that customers can customize).

## Model Definition

```python
class SoulTemplate(BaseModel):
    name: str
    archetype: str = "assistant"
    personality: dict[str, float]       # OCEAN traits, 0.0-1.0
    core_memories: list[str]
    skills: list[str]
    metadata: dict[str, Any]
    personality_variance: float = 0.1   # 0.0 = exact clone, 0.5 = max diversity
    name_prefix: str = ""               # e.g. "Agent-" -> "Agent-001"
```

### `personality`
A `dict[str, float]` rather than a fixed schema. This keeps the template layer neutral about which personality model the runtime uses. A PocketPaw runtime would populate `{"openness": 0.8, "conscientiousness": 0.6, ...}`; a custom runtime might use entirely different dimensions. Missing traits default to `0.5` by runtime convention (the spec doesn't enforce this, but the docstring documents it).

### `personality_variance`
Controls how much random deviation is applied to each trait when batch spawning. `Field(ge=0.0, le=0.5)` enforces the range at the spec layer — variance above `0.5` could invert trait polarity (a soul meant to be high-openness becomes low-openness), which is almost never the intended behavior.

### `core_memories`
A list of strings that get added to every spawned soul's memory store at creation. These are the "always remember" facts — the soul's mission statement, its name, the context it operates in. They ensure all spawned souls share the same foundational knowledge even when personality varies.

### `skills`
Names of skills to bootstrap in each spawned soul. The runtime resolves these names to actual skill objects; the template just holds the identifiers.

### `name_prefix`
When batch spawning, the factory generates names by combining this prefix with a zero-padded index: `"Agent-" -> "Agent-001", "Agent-002", ...`. An empty prefix means the template's `name` field is used as-is (appropriate when spawning a single soul).

## Usage Pattern

```python
template = SoulTemplate(
    name="Sales Assistant",
    archetype="sales_rep",
    personality={"openness": 0.7, "conscientiousness": 0.8},
    core_memories=["You are a sales assistant for Acme Corp."],
    skills=["crm_lookup", "email_draft"],
    personality_variance=0.1,
    name_prefix="Rep-"
)
# SoulFactory.spawn_batch(template, count=10) -> [Soul, Soul, ...]
```

## Data Flow

```
SoulTemplate
  └─ SoulFactory.spawn(template) -> Soul
       ├─ Identity created (name, traits + variance)
       ├─ core_memories added to MemoryStore
       └─ skills registered
```

## Known Gaps

- `SoulFactory` is referenced in the docstring but lives outside the spec layer. The template model itself is purely declarative — it has no `spawn()` method.
- `personality` traits missing from the dict default to `0.5` by documented convention, but this is not enforced by the model. A factory receiving a template with an empty personality dict would create a soul with all-neutral traits silently.