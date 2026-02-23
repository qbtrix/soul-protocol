<!-- README.md — Updated for emergent self-model and flexible configuration. -->

# Soul Protocol

The open standard for portable AI identity and memory.

## Installation

```bash
pip install soul-protocol
```

## Quick Start

```python
import asyncio
from soul_protocol import Soul, Interaction

async def main():
    # Birth a soul with full personality control
    soul = await Soul.birth(
        name="Aria",
        archetype="The Coding Expert",
        values=["precision", "clarity"],
        ocean={
            "openness": 0.8,
            "conscientiousness": 0.9,
            "neuroticism": 0.2,
        },
        communication={"warmth": "high", "verbosity": "low"},
        persona="I am Aria, a precise coding assistant.",
    )

    # Observe an interaction
    await soul.observe(Interaction(
        user_input="How do I optimize this SQL query?",
        agent_output="Add an index on the join column.",
    ))

    # The soul discovers its own identity from experience
    # (no hardcoded categories — domains emerge organically)
    images = soul.self_model.get_active_self_images()

    # Recall memories, generate prompts, export
    memories = await soul.recall("SQL optimization")
    prompt = soul.to_system_prompt()
    await soul.export("aria.soul")

asyncio.run(main())
```

Or birth from a config file:

```python
soul = await Soul.birth_from_config("soul-config.yaml")
```

```yaml
# soul-config.yaml
name: Aria
archetype: The Coding Expert
values: [precision, clarity, speed]
ocean:
  openness: 0.8
  conscientiousness: 0.9
  neuroticism: 0.2
communication:
  warmth: high
  verbosity: low
persona: I am Aria, precise and efficient.
```

## CLI

```bash
# Birth with personality flags
soul birth "Aria" --openness 0.8 --conscientiousness 0.9 -o aria.soul

# Birth from config file
soul birth --config soul-config.yaml

# Inspect
soul inspect aria.soul

# Export
soul export aria.soul -o aria.json -f json
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Flexible Config** | Full control over OCEAN personality, communication style, biorhythms via code, YAML, or CLI |
| **Emergent Self-Model** | Soul discovers its own identity from experience — no hardcoded categories |
| **5-Tier Memory** | Core, episodic, semantic, procedural, knowledge graph |
| **Psychology Pipeline** | Damasio somatic markers, LIDA significance, ACT-R activation, Klein self-concept |
| **Portable** | `.soul` file format — zip archive with identity, memory, and state |
| **LLM-Optional** | Works without any LLM via built-in heuristics. Plug in any LLM with `CognitiveEngine` |

## Documentation

- [Configuration Guide](docs/configuration.md) — OCEAN personality, communication style, config files, CLI options, presets
- [Self-Model Architecture](docs/self-model.md) — Emergent domain discovery, Klein's self-concept, confidence formula

## License

MIT
