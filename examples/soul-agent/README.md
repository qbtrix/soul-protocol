# Soul Agent — Claude Agent SDK + Soul Protocol

An interactive conversational agent that combines the **Claude Agent SDK** (agent loop, tool execution, streaming) with **Soul Protocol** (persistent identity, memory, personality).

The agent remembers what you tell it, learns from every conversation, and evolves its self-understanding over time.

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
```

### Quick birth (no config file)

```bash
python soul_agent.py --name Aria
python soul_agent.py --name Luna --archetype "The Creative Writer" --values "creativity,curiosity,empathy"
```

### Commands

- Type normally to chat
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
    -> Claude responds, optionally using soul tools
  -> Soul Protocol observes the interaction
    -> Sentiment detection (Damasio somatic markers)
    -> Mood update from sentiment (excited, concerned, curious, etc.)
    -> Significance gating (LIDA attention)
    -> Fact extraction -> semantic memory
    -> Entity extraction -> knowledge graph
    -> Self-model update (Klein self-concept)
  -> Auto-reflect every 5 turns
  -> Export .soul file on exit
```

## Soul Tools

The agent has 4 tools for interacting with its soul:

| Tool | Description |
|------|-------------|
| `soul_recall` | Search memories by natural language query |
| `soul_state` | Get current mood, energy, focus, social battery |
| `soul_reflect` | Trigger memory consolidation and self-reflection |
| `soul_remember` | Explicitly store a memory |

Claude uses these proactively — recalling past conversations when relevant, storing important facts, and monitoring its emotional state.

## Architecture

- **System prompt**: Generated from `soul.to_system_prompt()` — includes DNA (OCEAN personality), core memory, current state, and self-model insights
- **Observation loop**: After each exchange, `soul.observe()` runs the full psychology pipeline with sentiment-driven mood changes
- **Heuristic cognition**: Soul's internal processing uses `HeuristicEngine` (zero extra API calls)
- **Persistence**: `.soul` archive (zip of JSON/markdown) exported on exit, reloaded with `--soul`

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
