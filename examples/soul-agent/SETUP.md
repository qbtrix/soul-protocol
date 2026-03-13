# Soul Agent — Setup Steps

## 1. Install dependencies

```bash
cd examples/soul-agent
pip install -e ../..
pip install claude-agent-sdk
```

## 2. Set API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 3. Run (outside of Claude Code)

The Agent SDK launches Claude Code as a subprocess, so it **cannot run inside an existing Claude Code session**. Run from a normal terminal:

```bash
# Birth Aanya from config
python soul_agent.py --config anaya.yaml

# Resume from saved soul
python soul_agent.py --soul aanya.soul

# Resume encrypted soul
python soul_agent.py --soul aanya.soul --password secret

# Quick birth (no config)
python soul_agent.py --name Aria

# Custom archetype + values
python soul_agent.py --name Luna --archetype "The Creative Writer" --values "creativity,curiosity,empathy"

# Export with encryption
python soul_agent.py --name Aria --encrypt mypassword
```

## 4. Chat

- Type normally to chat
- `/bond` — view bond strength
- `/skills` — view skill levels and XP
- `/evolution` — view pending mutations and history
- `/reincarnate` — rebirth with new name (keeps memories)
- `/quit` to save and exit
- `Ctrl+C` to interrupt and save

The agent auto-exports a `.soul` file on exit (e.g. `aanya.soul`).

## 5. Available soul tools (15)

The agent exposes 15 MCP tools to Claude:

| Category | Tools |
|---|---|
| Memory | `soul_recall`, `soul_remember`, `soul_forget`, `soul_forget_entity` |
| Core Memory | `soul_core_memory`, `soul_edit_core_memory` |
| State | `soul_state`, `soul_feel` |
| Reflection | `soul_reflect`, `soul_self_model` |
| Skills | `soul_skills`, `soul_grant_xp` |
| Evolution | `soul_propose_evolution`, `soul_approve_evolution` |
| System | `soul_prompt` |
