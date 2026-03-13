<!-- Guide: soul inject — fast context injection for AI agents.
     Covers: why inject vs MCP, setup, usage for each platform, automation,
     team workflows, CI/CD, and combining inject with MCP.
     Created: 2026-03-13 -->

# Guide: Fast Agent Integration with `soul inject`

`soul inject` writes your soul's identity, memories, and state directly into your AI agent's config file. One command, ~50ms, no server needed.

## Why `soul inject`?

MCP servers are powerful but heavy. They need a running process, can disconnect, and add latency to every tool call. For many workflows, you just want the agent to *know who it is* when it starts up.

`soul inject` gives you that:

| | MCP Server | `soul inject` |
|---|---|---|
| Speed | ~500ms per call | ~50ms total |
| Reliability | Can crash/disconnect | Always works |
| Setup | Config JSON, env vars | One command |
| Offline | Needs server process | Works offline |
| Real-time memory | Yes | No (static snapshot) |
| Memory updates mid-chat | Yes | No |

**Use both together**: `soul inject` for baseline context on startup, MCP for live memory during conversation.

## Quick Start

```bash
# 1. Create a soul (if you haven't already)
soul init "Aria" --archetype "The Coding Expert"

# 2. Inject into your agent's config
soul inject claude-code
```

That's it. Your `.claude/CLAUDE.md` now contains Aria's identity, personality, current state, and recent memories.

## What Gets Injected

The command writes a markdown block like this into your config file:

```markdown
<!-- SOUL-CONTEXT-START -->
## Soul: Aria

**Identity**: Aria, The Coding Expert. DID: did:soul:aria-a3f2b1
**Values**: precision, clarity, empathy
**State**: curious, 95% energy, active

### Core Memory
**Persona**: I am Aria, a precise and clear-thinking coding assistant...
**Human**: Prakash is a solo founder working on PocketPaw and Soul Protocol...

### Recent Context (5 memories)
- [episodic] User asked about FastAPI middleware patterns (importance: 7)
- [episodic] Discussed async Python testing strategies (importance: 8)
- [episodic] User prefers minimal dependencies (importance: 6)
...

_Injected by `soul inject` at 2026-03-13T12:00:00Z_
<!-- SOUL-CONTEXT-END -->
```

The `<!-- SOUL-CONTEXT-START/END -->` markers make it idempotent. Running `soul inject` again replaces the block without duplicating it. Your existing config content is preserved.

## Platform-by-Platform Setup

### Claude Code

```bash
soul inject claude-code
# Writes to: .claude/CLAUDE.md
```

If you already have a `CLAUDE.md` with project instructions, the soul context is appended (or replaces the previous injection). Your existing instructions stay untouched.

### Cursor

```bash
soul inject cursor
# Writes to: .cursorrules
```

### VS Code / GitHub Copilot

```bash
soul inject vscode
# Writes to: .github/copilot-instructions.md
```

Creates the `.github/` directory if it doesn't exist.

### Windsurf

```bash
soul inject windsurf
# Writes to: .windsurfrules
```

### Cline

```bash
soul inject cline
# Writes to: .clinerules
```

### Continue

```bash
soul inject continue
# Writes to: .continuerules
```

## Options

### Choose a specific soul

If your `.soul/` directory contains multiple souls (e.g., `guardian/` and `pocketpaw.soul`):

```bash
soul inject claude-code --soul guardian
soul inject cursor --soul pocketpaw
```

### Custom soul directory

```bash
soul inject claude-code --dir ~/projects/my-app/.soul
soul inject cursor --dir /absolute/path/to/souls
```

### Control memory count

```bash
# Include 20 recent memories (default: 10)
soul inject claude-code --memories 20

# Minimal context (identity + state only, no memories)
soul inject claude-code --memories 0
```

### Quiet mode

```bash
soul inject claude-code --quiet
```

Suppresses the "Injected soul context into..." confirmation message. Useful in scripts.

## Workflows

### Daily refresh

Re-inject each morning to pick up memories from yesterday's sessions:

```bash
soul inject claude-code
```

If you used MCP during yesterday's session, the soul auto-saved new memories. Running `soul inject` today picks them up.

### Multi-platform development

Inject the same soul into every editor you use:

```bash
soul inject claude-code
soul inject cursor
soul inject vscode
soul inject windsurf
```

All four editors now share the same soul context. When you switch editors, your agent already knows who you are and what you've been working on.

### Team workflows

Commit the `.soul/` directory to git. Each team member runs:

```bash
git pull
soul inject claude-code
```

Everyone's agent starts with the same baseline identity and shared context. Individual sessions can still use MCP for personal memory.

### CI/CD integration

Add `soul inject` to your CI pipeline to ensure agents always have fresh context:

```bash
# In your CI script or Makefile
soul inject claude-code --dir .soul --quiet
```

### Shell alias

Add to your `.zshrc` or `.bashrc`:

```bash
alias si="soul inject claude-code"
```

Now just type `si` to refresh your agent's context.

### Git hook

Auto-inject after every `git checkout` or `git pull`:

```bash
# .git/hooks/post-checkout
#!/bin/sh
soul inject claude-code --quiet 2>/dev/null || true
```

## Combining with MCP

The best setup uses both:

1. **`soul inject`** at session start for fast baseline context
2. **MCP server** running for live memory operations during the session

```bash
# Setup (one time)
soul init "Aria" --setup claude-code

# Each session
soul inject claude-code   # fast context refresh
# ... then Claude Code connects to MCP for soul_observe, soul_remember, etc.
```

The injected context gives the agent immediate awareness. MCP gives it the ability to learn and evolve during the conversation.

## Troubleshooting

### "Soul directory not found"

Make sure you've run `soul init` first, or point `--dir` to where your soul lives:

```bash
soul inject claude-code --dir /path/to/.soul
```

### "No soul found in .soul/"

The directory exists but doesn't contain a `soul.json` (directory format) or `.soul` file (ZIP format). Run `soul init` to create one.

### Context looks stale

The inject command reads from disk. If you used MCP during your last session, make sure the MCP server shut down cleanly (it auto-saves on exit). Then re-run `soul inject` to pick up the latest state.

### Existing config content disappeared

This shouldn't happen -- `soul inject` only replaces content between `<!-- SOUL-CONTEXT-START -->` and `<!-- SOUL-CONTEXT-END -->` markers. If your config file had no markers, the block is appended. If you accidentally deleted content, check git history.
