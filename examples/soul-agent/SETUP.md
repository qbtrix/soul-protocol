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

# Quick birth (no config)
python soul_agent.py --name Aria

# Custom archetype + values
python soul_agent.py --name Luna --archetype "The Creative Writer" --values "creativity,curiosity,empathy"
```

## 4. Chat

- Type normally to chat
- `/quit` to save and exit
- `Ctrl+C` to interrupt and save

The agent auto-exports a `.soul` file on exit (e.g. `aanya.soul`).
