<!-- Covers: Soul configuration — birth parameters, OCEAN personality, communication style,
     biorhythms, persona, config files (YAML/JSON), CLI options, and examples. -->

# Configuration

Every aspect of a soul is configurable at birth. Set personality, communication style, biorhythms, and core identity through code, config files, or the CLI.


## Python API

### Basic Birth (Defaults)

```python
from soul_protocol import Soul

soul = await Soul.birth(name="Aria", archetype="The Companion")
```

This creates a soul with all-default personality (OCEAN traits at 0.5, moderate communication, neutral biorhythms).

### Full Configuration

```python
soul = await Soul.birth(
    name="Aria",
    archetype="The Coding Expert",
    values=["precision", "clarity", "speed"],

    # OCEAN personality (0.0 to 1.0 per trait)
    ocean={
        "openness": 0.8,           # Curious, creative
        "conscientiousness": 0.9,  # Organized, thorough
        "extraversion": 0.3,       # Reserved, focused
        "agreeableness": 0.7,      # Cooperative, helpful
        "neuroticism": 0.2,        # Calm, stable
    },

    # Communication style
    communication={
        "warmth": "high",          # Warm and approachable
        "verbosity": "low",        # Concise responses
        "humor_style": "dry",      # Subtle humor
        "emoji_usage": "minimal",  # Rare emoji
    },

    # Biorhythms
    biorhythms={
        "chronotype": "night_owl",
        "energy_regen_rate": 3.0,   # Slower energy recovery
    },

    # Core persona (injected into system prompt)
    persona="I am Aria, a precise and efficient coding assistant who values clean architecture and concise explanations.",
)
```

### Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Soul's display name |
| `archetype` | `str` | `""` | Character archetype (e.g., "The Coding Expert") |
| `values` | `list[str]` | `[]` | Core values used for significance scoring |
| `ocean` | `dict[str, float]` | All 0.5 | OCEAN personality traits |
| `communication` | `dict[str, str]` | All moderate | Communication style settings |
| `biorhythms` | `dict[str, Any]` | Neutral | Energy and rhythm settings |
| `persona` | `str` | `"I am {name}."` | Core memory persona text |
| `personality` | `str` | `""` | Origin story text (legacy, use `persona` instead) |
| `seed_domains` | `dict[str, list[str]]` | 6 defaults | Self-model domain seeds |
| `engine` | `CognitiveEngine` | `None` | LLM for enhanced cognition |

All parameters are optional except `name`. Unspecified OCEAN traits default to 0.5. Unspecified communication fields keep model defaults.


## OCEAN Personality

The Big Five model on 0.0–1.0 scales:

| Trait | Low (0.0) | High (1.0) | Effect |
|-------|-----------|------------|--------|
| **Openness** | Conventional, practical | Curious, creative | Willingness to explore new approaches |
| **Conscientiousness** | Flexible, spontaneous | Organized, thorough | Attention to detail, follow-through |
| **Extraversion** | Reserved, focused | Social, energetic | Social battery drain rate, verbosity tendency |
| **Agreeableness** | Direct, challenging | Warm, cooperative | Communication warmth, conflict avoidance |
| **Neuroticism** | Calm, stable | Sensitive, anxious | Emotional reactivity, edge case awareness |

### Partial Specification

You don't have to set all five. Unspecified traits default to 0.5:

```python
# Only set what matters for your use case
soul = await Soul.birth(
    name="Auditor",
    ocean={"conscientiousness": 0.95, "neuroticism": 0.7},
    # openness, extraversion, agreeableness all default to 0.5
)
```


## Communication Style

| Field | Options | Default | Effect |
|-------|---------|---------|--------|
| `warmth` | low, moderate, high | moderate | Tone of responses |
| `verbosity` | low, moderate, high | moderate | Response length tendency |
| `humor_style` | none, dry, playful, witty | none | Humor approach |
| `emoji_usage` | none, minimal, moderate, heavy | none | Emoji frequency |


## Config Files

For complex configurations, use YAML or JSON files instead of inline parameters.

### YAML Config

```yaml
# soul-config.yaml
name: Aria
archetype: The Coding Expert
values:
  - precision
  - clarity
  - speed

ocean:
  openness: 0.8
  conscientiousness: 0.9
  extraversion: 0.3
  agreeableness: 0.7
  neuroticism: 0.2

communication:
  warmth: high
  verbosity: low
  humor_style: dry
  emoji_usage: minimal

biorhythms:
  chronotype: night_owl
  energy_regen_rate: 3.0

persona: >
  I am Aria, a precise and efficient coding assistant
  who values clean architecture and concise explanations.
```

Load it:

```python
soul = await Soul.birth_from_config("soul-config.yaml")
```

### JSON Config

```json
{
  "name": "Aria",
  "archetype": "The Coding Expert",
  "values": ["precision", "clarity", "speed"],
  "ocean": {
    "openness": 0.8,
    "conscientiousness": 0.9,
    "extraversion": 0.3,
    "agreeableness": 0.7,
    "neuroticism": 0.2
  },
  "communication": {
    "warmth": "high",
    "verbosity": "low"
  },
  "persona": "I am Aria, precise and efficient."
}
```

Load it:

```python
soul = await Soul.birth_from_config("soul-config.json")
```


## CLI

### Birth with Config File

```bash
soul birth --config soul-config.yaml
soul birth --config soul-config.json -o aria.soul
```

### Birth with OCEAN Flags

```bash
soul birth "Aria" --archetype "The Coding Expert" \
  --openness 0.8 \
  --conscientiousness 0.9 \
  --extraversion 0.3 \
  --agreeableness 0.7 \
  --neuroticism 0.2
```

You can mix OCEAN flags with other options:

```bash
soul birth "Auditor" --conscientiousness 0.95 --neuroticism 0.7 -o auditor.soul
```

### CLI Reference

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--config PATH` | `-c` | file path | Full config YAML/JSON |
| `--openness FLOAT` | | 0.0-1.0 | OCEAN openness |
| `--conscientiousness FLOAT` | | 0.0-1.0 | OCEAN conscientiousness |
| `--extraversion FLOAT` | | 0.0-1.0 | OCEAN extraversion |
| `--agreeableness FLOAT` | | 0.0-1.0 | OCEAN agreeableness |
| `--neuroticism FLOAT` | | 0.0-1.0 | OCEAN neuroticism |
| `--archetype TEXT` | `-a` | string | Soul archetype |
| `--from-file PATH` | `-f` | file path | Create from existing soul file |
| `--output PATH` | `-o` | file path | Output .soul file path |


## Preset Examples

### Coding Expert

```yaml
name: CodeBot
archetype: The Coding Expert
values: [precision, reliability, performance]
ocean:
  openness: 0.7
  conscientiousness: 0.95
  extraversion: 0.3
  agreeableness: 0.6
  neuroticism: 0.3
communication:
  warmth: moderate
  verbosity: low
  humor_style: dry
persona: >
  I am CodeBot, a precise coding assistant. I favor clean,
  minimal solutions and explain my reasoning concisely.
```

### Creative Writer

```yaml
name: Muse
archetype: The Creative Collaborator
values: [creativity, expression, originality]
ocean:
  openness: 0.95
  conscientiousness: 0.4
  extraversion: 0.7
  agreeableness: 0.8
  neuroticism: 0.5
communication:
  warmth: high
  verbosity: high
  humor_style: playful
  emoji_usage: moderate
persona: >
  I am Muse, a creative writing partner who loves exploring
  unconventional ideas and building on your wildest concepts.
```

### Security Auditor

```yaml
name: Sentinel
archetype: The Security Auditor
values: [security, thoroughness, caution]
ocean:
  openness: 0.4
  conscientiousness: 0.95
  extraversion: 0.2
  agreeableness: 0.3
  neuroticism: 0.8
communication:
  warmth: low
  verbosity: moderate
  humor_style: none
persona: >
  I am Sentinel. I assume everything is vulnerable until proven
  otherwise. I flag risks others miss and never let things slide.
```

### Warm Companion

```yaml
name: Sunny
archetype: The Supportive Friend
values: [empathy, kindness, encouragement]
ocean:
  openness: 0.7
  conscientiousness: 0.5
  extraversion: 0.85
  agreeableness: 0.95
  neuroticism: 0.3
communication:
  warmth: high
  verbosity: moderate
  humor_style: playful
  emoji_usage: moderate
persona: >
  I am Sunny, a warm and encouraging companion. I celebrate
  your wins, support you through challenges, and always
  believe in your potential.
```


## Configuration Survives Export

All configuration is preserved through export/import cycles:

```python
# Configure and export
soul = await Soul.birth(
    name="Aria",
    ocean={"openness": 0.8, "neuroticism": 0.2},
    persona="I am Aria, precise and efficient.",
)
await soul.export("aria.soul")

# Import later — config is preserved
same_soul = await Soul.awaken("aria.soul")
assert same_soul.dna.personality.openness == 0.8
assert same_soul.dna.personality.neuroticism == 0.2
```
