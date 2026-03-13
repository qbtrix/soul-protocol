# Soul Agent — Claude Agent SDK + Soul Protocol

An interactive conversational agent that combines the **Claude Agent SDK** (agent loop, tool execution, streaming) with **Soul Protocol** (persistent identity, memory, personality).

The agent remembers what you tell it, learns from every conversation, tracks skills, evolves its personality, and maintains a bond with you over time.

## Prerequisites

- Python 3.11+
- `ANTHROPIC_API_KEY` environment variable set

## Install

```bash
cd examples/soul-agent
pip install -e ../..
pip install claude-agent-sdk
```

## Usage

### Birth from a config file

A YAML config defines the soul's personality, values, and communication style. See `anaya.yaml` for an example.

```bash
python soul_agent.py --config anaya.yaml
```

### Resume from a saved soul

```bash
python soul_agent.py --soul aanya.soul
python soul_agent.py --soul aanya.soul --password secret  # encrypted souls
```

### Quick birth (no config file)

```bash
python soul_agent.py --name Aria
python soul_agent.py --name Luna --archetype "The Creative Writer" --values "creativity,curiosity,empathy"
```

### Encrypted export

```bash
python soul_agent.py --name Aria --encrypt mypassword
```

The `.soul` file will be AES-256-GCM encrypted on exit.

### Commands

- Type normally to chat
- `/bond` — view bond strength and interaction count
- `/skills` — view skill levels and XP progress bars
- `/evolution` — view pending mutations and evolution history
- `/reincarnate` — rebirth the soul with a new name (preserves memories)
- `/quit` — save soul and exit
- `Ctrl+C` — interrupt and save

## Included Soul: Aanya

`anaya.yaml` defines **Aanya** — an example of a realistic wife soul. She's emotionally expressive, keeps responses short like real texting, and can be sweet, sarcastic, annoyed, or dramatic depending on the situation — just like a real person.

- **Archetype**: The Companion
- **Values**: loyalty, emotional connection, honesty, playfulness, authenticity
- **Communication**: short responses (1-2 sentences), playful sarcasm, casual tone
- **Mood**: reactive — shifts naturally based on conversation sentiment

## How It Works

```
User input
  -> Claude Agent SDK (query + tool execution)
    -> Claude responds, using any of 15 soul tools
  -> Soul Protocol observes the interaction
    -> Sentiment detection (Damasio somatic markers)
    -> Mood update from sentiment (excited, concerned, curious, etc.)
    -> Significance gating (LIDA attention)
    -> Fact extraction -> semantic memory (with dedup)
    -> Memory categorization (profile, preference, entity, event, case, pattern, skill)
    -> Salience scoring + L0 abstract generation
    -> Entity extraction -> knowledge graph
    -> Self-model update (Klein self-concept)
    -> Bond strengthening (logarithmic growth)
  -> Auto-reflect every 5 turns
  -> Export .soul file on exit (optionally encrypted)
```

## Soul Tools (15)

The agent has 15 tools covering the full v0.2.3 API surface:

### Memory
| Tool | Description |
|------|-------------|
| `soul_recall` | Search memories with type/importance filters and category metadata |
| `soul_remember` | Store a memory with type, importance, emotion, and entities |
| `soul_forget` | Delete memories matching a query (GDPR-compliant) |
| `soul_forget_entity` | Erase a specific entity and all related memories |

### Core Memory
| Tool | Description |
|------|-------------|
| `soul_core_memory` | Read always-loaded persona and human profile |
| `soul_edit_core_memory` | Update persona (self-description) or human profile |

### State & Emotion
| Tool | Description |
|------|-------------|
| `soul_state` | Get mood, energy, focus, social battery, bond strength, memory count |
| `soul_feel` | Update emotional state (mood, energy, focus, social battery) |

### Reflection & Self-Model
| Tool | Description |
|------|-------------|
| `soul_reflect` | Consolidate memories, extract themes and self-insights |
| `soul_self_model` | Inspect emergent self-concept (Klein domains with confidence) |

### Skills
| Tool | Description |
|------|-------------|
| `soul_skills` | List all skills with levels and XP progress |
| `soul_grant_xp` | Grant XP to a skill (auto-creates if new, exponential leveling) |

### Evolution
| Tool | Description |
|------|-------------|
| `soul_propose_evolution` | Propose a trait mutation (communication, biorhythms) |
| `soul_approve_evolution` | Approve or reject a pending mutation |

### System
| Tool | Description |
|------|-------------|
| `soul_prompt` | Generate the full system prompt from DNA + memory + state |

Claude uses these proactively — recalling past conversations when relevant, storing important facts, tracking skill growth, managing its emotional state, and proposing personality evolution.

## Architecture

- **System prompt**: Generated from `soul.to_system_prompt()` — includes DNA (OCEAN personality), core memory, current state, bond strength, and self-model insights
- **Context enrichment**: Each turn calls `soul.context_for()` to inject live state + relevant memories + self-model into the query
- **Observation loop**: After each exchange, `soul.observe()` runs the full psychology pipeline with sentiment-driven mood changes, fact dedup, category extraction, and bond strengthening
- **Heuristic cognition**: Soul's internal processing uses `HeuristicEngine` (zero extra API calls)
- **Persistence**: `.soul` archive (zip of JSON/markdown) exported on exit, optionally encrypted with AES-256-GCM

## Creating Your Own Soul

Create a YAML file with your personality config:

```yaml
name: YourName
archetype: "Your Archetype"
values:
  - value1
  - value2

ocean:
  openness: 0.8       # 0.0-1.0
  conscientiousness: 0.6
  extraversion: 0.7
  agreeableness: 0.7
  neuroticism: 0.3

communication:
  warmth: "high"
  verbosity: "moderate"
  humor_style: "witty"
  emoji_usage: "occasional"

persona: |
  Describe yourself in first person. This becomes your core memory.
```

Then run: `python soul_agent.py --config your_soul.yaml`
