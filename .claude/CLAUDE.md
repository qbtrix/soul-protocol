# Soul

## Soul (Persistent Memory)

This project uses [Soul Protocol](https://github.com/qbtrix/soul-protocol) for persistent AI memory via MCP.

**On session start:**
1. Call `soul_recall` with the current task context to load relevant memories
2. Call `soul_state` to check current mood and energy
3. Call `soul_list` to see all loaded souls (multi-soul support via `SOUL_DIR`)

**During work:**
- `soul_observe` after key decisions, completed tasks, or important conversations
- `soul_remember` for facts that should persist across sessions
- `soul_feel` to update emotional state after significant events
- `soul_prompt` to generate a system prompt for LLM injection

**On session end:**
- The soul auto-saves on shutdown — no manual save needed

**Agent integration:**
- Use `soul inject --target claude-code` to inject soul context into `.claude/CLAUDE.md`
- Supported targets: `claude-code`, `cursor`, `vscode`, `windsurf`, `cline`, `continue`
- Injection is idempotent (marker-based replacement)
