# Soul

## Soul (Persistent Memory)

This project uses [Soul Protocol](https://github.com/qbtrix/soul-protocol) for persistent AI memory via MCP.

**On session start:**
1. Call `soul_recall` with the current task context to load relevant memories
2. Call `soul_state` to check current mood and energy
3. Call `soul_list` to see all loaded souls (multi-soul support via `SOUL_DIR`)

**During work:**
- `soul_observe` after key decisions, completed tasks, or important conversations — runs the full pipeline (extracts facts, reconciles against existing entries, updates self-model). Prefer this whenever a fact comes out of a real user/agent turn, since it deduplicates as it stores.
- `soul_remember` only for blunt writes you want to force through: short episodic events, or cases where you've already decided dedup is wrong (e.g. a unique timestamped log line). It appends without `reconcile_fact`, so repeated calls with similar text will accumulate near-duplicates. The CLI sibling `soul remember` is on a deprecation path toward `soul note` (#231 phase 2); the MCP tool will follow once the dedup-aware variant is exposed there.
- `soul_feel` to update emotional state after significant events
- `soul_prompt` to generate a system prompt for LLM injection

**On session end:**
- The soul auto-saves on shutdown — no manual save needed

**Agent integration:**
- Use `soul inject --target claude-code` to inject soul context into `.claude/CLAUDE.md`
- Supported targets: `claude-code`, `cursor`, `vscode`, `windsurf`, `cline`, `continue`
- Injection is idempotent (marker-based replacement)
