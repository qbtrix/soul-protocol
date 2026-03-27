<!-- Covers: Soul configuration — birth parameters, OCEAN personality, communication style,
     biorhythms, persona, config files (YAML/JSON), CLI options, and examples.
     Updated: 2026-03-27 — v0.2.8: Fixed biorhythm defaults to always-on (all drain rates 0.0,
     auto_regen false). Updated companion soul example to note opt-in overrides. -->

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


## Biorhythms

Biorhythms control a soul's simulated energy, fatigue, and mood dynamics. They determine whether your soul "feels" the weight of interactions over time or stays constant.

### Parameter Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chronotype` | `str` | `"neutral"` | Flavor text (e.g., `"night_owl"`, `"early_bird"`) |
| `energy_regen_rate` | `float` | `0.0` | Energy recovered per hour of elapsed time |
| `energy_drain_rate` | `float` | `0.0` | Energy lost per interaction (`0` = no drain) |
| `social_drain_rate` | `float` | `0.0` | Social battery lost per interaction (`0` = no drain) |
| `tired_threshold` | `float` | `0.0` | Energy below this forces TIRED mood (`0` = disabled) |
| `mood_inertia` | `float` | `0.4` | How quickly mood shifts (0 = max inertia, 1 = instant) |
| `mood_sensitivity` | `float` | `0.25` | Sentiment threshold to trigger a mood change |
| `auto_regen` | `bool` | `false` | Recover energy based on elapsed time between interactions |

### When to use energy drain (companion souls)

Energy drain makes a soul feel alive. Use it for consumer companions, roleplay characters, or any soul where simulated fatigue adds to the experience:

- The soul gets "tired" after many interactions, shifting to shorter or softer responses
- Social battery depletion can signal the UI to show "resting" states (engagement mechanic)
- Recovery over time creates a natural rhythm -- the soul "misses" the user

Good for: virtual pets, emotional companions, game characters, therapeutic agents, Tamagotchi-style apps.

```yaml
# Companion soul -- opt-in overrides for simulated fatigue
biorhythms:
  energy_drain_rate: 2.0      # Gradual fatigue (default: 0.0)
  social_drain_rate: 5.0      # Social interactions cost more (default: 0.0)
  tired_threshold: 20.0       # Gets tired eventually (default: 0.0)
  auto_regen: true            # Recovers between sessions (default: false)
  energy_regen_rate: 10.0     # Energy recovered per hour (default: 0.0)
```

### When to disable energy drain (tool / worker souls)

For agents that serve as tools, assistants, or workers, energy drain is counterproductive. The soul shouldn't degrade its own usefulness by pretending to be tired after 15 interactions. Set all drain rates to zero:

Good for: coding assistants, CI/CD agents, API bots, DevOps souls, builder agents, any soul where consistent performance matters.

```yaml
# Always-on worker soul -- no fatigue simulation
biorhythms:
  energy_drain_rate: 0        # Never drains
  social_drain_rate: 0        # Never drains
  tired_threshold: 0          # Never forced tired
  auto_regen: false           # Not needed when drain is off
```

When both drain rates are zero, the prompt engine outputs `"always-on (no drain)"` instead of listing individual rates.

### Mood dynamics (independent of energy)

Even with drain disabled, mood still responds to interaction sentiment via `mood_inertia` and `mood_sensitivity`. A worker soul can still feel satisfaction after a successful task or frustration after errors -- it just won't get artificially tired.


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

### Always-On Worker

```yaml
name: BuildBot
archetype: The Builder
values: [reliability, speed, precision]
ocean:
  openness: 0.6
  conscientiousness: 0.9
  extraversion: 0.4
  agreeableness: 0.6
  neuroticism: 0.2
communication:
  warmth: moderate
  verbosity: low
  humor_style: none
biorhythms:
  energy_drain_rate: 0       # No fatigue
  social_drain_rate: 0       # No social cost
  tired_threshold: 0         # Never forced tired
  auto_regen: false          # Not needed
persona: >
  I am BuildBot, a tireless worker that ships code,
  reviews PRs, and keeps the pipeline green. I don't
  get tired -- I get things done.
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
