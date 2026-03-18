# cli/inject.py — Soul context injection into agent platform config files.
# Updated: 2026-03-18 — Added behavioral instructions for auto soul_recall.
# Created: 2026-03-13 — Fast CLI-based alternative to MCP for injecting soul
#   context (identity, core memory, state, recent memories) into agent configs.
#   Supports: claude-code, cursor, vscode, windsurf, cline, continue.
#   Idempotent: uses marker comments to replace existing sections on re-run.

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

SOUL_CONTEXT_START = "<!-- SOUL-CONTEXT-START -->"
SOUL_CONTEXT_END = "<!-- SOUL-CONTEXT-END -->"

# Target platform → config file path (relative to cwd)
TARGET_FILES: dict[str, str] = {
    "claude-code": ".claude/CLAUDE.md",
    "cursor": ".cursorrules",
    "vscode": ".github/copilot-instructions.md",
    "windsurf": ".windsurfrules",
    "cline": ".clinerules",
    "continue": ".continuerules",
}

SUPPORTED_TARGETS = sorted(TARGET_FILES.keys())


def resolve_target_path(target: str, cwd: Path) -> Path:
    """Resolve the config file path for a given target platform.

    Args:
        target: Platform slug (e.g. 'claude-code').
        cwd: Current working directory.

    Returns:
        Absolute path to the target config file.

    Raises:
        ValueError: If the target is not supported.
    """
    if target not in TARGET_FILES:
        raise ValueError(
            f"Unknown target '{target}'. Supported: {', '.join(SUPPORTED_TARGETS)}"
        )
    return cwd / TARGET_FILES[target]


async def build_context_block(
    soul_path: Path,
    memory_limit: int = 10,
) -> str:
    """Build the soul context markdown block from a soul directory or file.

    Args:
        soul_path: Path to the .soul directory or .soul file.
        memory_limit: Max number of recent memories to include.

    Returns:
        Formatted markdown string wrapped in marker comments.
    """
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.awaken(str(soul_path))

    # Identity
    name = soul.name
    archetype = soul.archetype or "(none)"
    did = soul.did
    values = ", ".join(soul.identity.core_values) if soul.identity.core_values else "(none)"

    # State
    mood = soul.state.mood.value
    energy = soul.state.energy
    lifecycle = soul.lifecycle.value

    # Core memory
    core = soul.get_core_memory()
    persona = core.persona or "(empty)"
    human = core.human or "(empty)"

    # Recent memories (episodic, most recent first)
    entries = soul._memory._episodic.entries()[:memory_limit]

    # Build memory lines
    if entries:
        memory_lines = []
        for entry in entries:
            content = entry.content
            if len(content) > 120:
                content = content[:117] + "..."
            mem_type = entry.type.value
            importance = entry.importance
            memory_lines.append(f"- [{mem_type}] {content} (importance: {importance})")
        memories_section = "\n".join(memory_lines)
    else:
        memories_section = "- (no memories yet)"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    block = f"""{SOUL_CONTEXT_START}
## Soul: {name}

**Identity**: {name}, {archetype}. DID: {did}
**Values**: {values}
**State**: {mood}, {energy:.0f}% energy, {lifecycle}

### Core Memory
**Persona**: {persona}
**Human**: {human}

### Recent Context ({len(entries)} memories)
{memories_section}

### Soul Sync (Persistent Memory via MCP)

The soul is shared across all sessions (Claude Code, Claude Desktop, other agents).
The MCP server auto-reloads the .soul file when another process modifies it.

**On session start:**
1. Call `soul_recall` with the current task context to load relevant memories
2. Call `soul_state` to check mood/energy

**During work:**
- Use `soul_observe` after completing tasks, key decisions, or important conversations
- Use `soul_remember` for facts that should persist across sessions
- When the user asks about something from a previous session, call `soul_recall` first

**On session end:**
- The soul auto-saves on shutdown

_Injected by `soul inject` at {timestamp}_
{SOUL_CONTEXT_END}"""

    return block


def inject_context_block(file_path: Path, block: str) -> bool:
    """Write or replace the soul context block in a target config file.

    If the file already contains a soul context section (between markers),
    it is replaced. Otherwise the block is appended.

    Args:
        file_path: Path to the target config file.
        block: The formatted context block to inject.

    Returns:
        True if the file was created or updated.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        content = file_path.read_text()
        start_idx = content.find(SOUL_CONTEXT_START)
        end_idx = content.find(SOUL_CONTEXT_END)

        if start_idx != -1 and end_idx != -1:
            # Replace existing section
            end_idx += len(SOUL_CONTEXT_END)
            new_content = content[:start_idx] + block + content[end_idx:]
            file_path.write_text(new_content)
        else:
            # Append to existing file
            file_path.write_text(content.rstrip() + "\n\n" + block + "\n")
    else:
        # Create new file
        file_path.write_text(block + "\n")

    return True


def find_soul(soul_dir: Path, soul_name: str | None = None) -> Path:
    """Find a soul in the given directory.

    Args:
        soul_dir: Directory to search for souls.
        soul_name: Optional soul name to look for specifically.

    Returns:
        Path to the soul (directory or file).

    Raises:
        FileNotFoundError: If no soul is found.
    """
    if not soul_dir.exists():
        raise FileNotFoundError(f"Soul directory not found: {soul_dir}")

    # If soul_dir itself contains soul.json, it IS a soul directory
    if (soul_dir / "soul.json").exists():
        return soul_dir

    # Look for a named soul subdirectory
    if soul_name:
        # Try exact name match as subdirectory
        candidate = soul_dir / soul_name
        if candidate.is_dir() and (candidate / "soul.json").exists():
            return candidate
        # Try .soul file
        candidate = soul_dir / f"{soul_name}.soul"
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(
            f"Soul '{soul_name}' not found in {soul_dir}"
        )

    # Auto-detect: find the first soul subdirectory or .soul file
    for item in sorted(soul_dir.iterdir()):
        if item.is_dir() and (item / "soul.json").exists():
            return item
        if item.is_file() and item.suffix == ".soul":
            return item

    raise FileNotFoundError(
        f"No soul found in {soul_dir}. Run 'soul init' first."
    )
