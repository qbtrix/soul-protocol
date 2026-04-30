# soul_protocol.mcp.server — FastMCP server for soul-protocol
# 32 tools (27 soul + 5 context), 3 resources, 2 prompts for AI agent integration
# Updated: 2026-04-30 (#203) — Touch-time chain pruning: ``soul_prune_chain``
#   compresses a soul's old trust-chain history into a signed chain.pruned
#   marker. Defaults to dry-run; pass ``apply=True`` to mutate the chain.
#   Defers the full archival design to v0.5.x.
# Updated: 2026-04-29 (#160) — `soul_eval` tool runs a YAML eval spec against
#   the active soul (no birth, no seed) so agents can self-evaluate their
#   current state. Accepts yaml_path or yaml_string. Returns the EvalResult
#   as JSON.
# Updated: 2026-04-29 (#42) — Trust chain tools: ``soul_verify`` returns chain
#   integrity status; ``soul_audit`` returns the human-readable timeline of
#   signed actions, with optional action_prefix and limit. JSON-only output —
#   designed for agent consumption.
# Updated: 2026-04-29 (#46) — Multi-user soul support. ``soul_observe`` and
#   ``soul_recall`` accept an optional ``user_id`` parameter that pipes
#   through to the runtime so memories get attributed and recall results
#   filter by user. The recall payload now carries ``user_id`` per entry
#   so consumers can render multi-user views.
# Updated: 2026-04-06 — Added soul_dream tool for offline batch memory consolidation.
#   Detects topic clusters, recurring procedures, behavioral trends, consolidates
#   graph, and proposes personality evolution.
# Updated: 2026-03-27 — Added 4 tools: soul_forget, soul_edit_core, soul_health,
#   soul_cleanup. MCP now has full feature parity with CLI maintenance commands (v0.2.8).
# Updated: 2026-03-26 — Added 5 psychology pipeline tools: soul_skills, soul_evaluate,
#   soul_learn, soul_evolve, soul_bond. MCP now has feature parity with CLI for the
#   psychology subsystem fixed in v0.2.7.
# Updated: 2026-03-24 — Auto-detect .soul/ in CWD or ~/.soul/ when no env var set.
# Updated: feat/mcp-sampling-engine — Lazy MCPSamplingEngine wiring. On the first tool
#   call that carries a FastMCP Context, MCPSamplingEngine is constructed and pushed to
#   all loaded souls via Soul.set_engine(). Subsequent calls reuse the same engine.
#   Tools that do cognitive work (soul_observe, soul_reflect, soul_birth, soul_state)
#   accept ctx: Context so the engine can be lazily wired.
# Updated: 2026-03-18 — Auto-reload: detect external .soul file changes via mtime check.
# Updated: 2026-03-15 — Added soul_reload tool to pick up external .soul file changes.
# Updated: 2026-03-13 — Multi-soul support via SoulRegistry + SOUL_DIR scanning.
#
# Usage:
#   SOUL_DIR=.soul/ soul-mcp          # load all souls from directory
#   SOUL_PATH=aria.soul soul-mcp      # load single soul (backward compat)
#   Or call soul_birth to create a new soul at runtime

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP  # optional dep: pip install soul-protocol[mcp]

from ..runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine
from ..runtime.context import LCMContext
from ..runtime.exceptions import SoulProtocolError
from ..runtime.soul import Soul
from ..runtime.types import Interaction, MemoryType, Mood

# ── Soul Registry ──


class SoulRegistry:
    """Manages multiple souls with an active soul pointer."""

    def __init__(self) -> None:
        self._souls: dict[str, Soul] = {}  # lowercase name -> Soul
        self._paths: dict[str, str] = {}  # lowercase name -> source path
        self._formats: dict[str, str] = {}  # lowercase name -> "directory" | "zip"
        self._mtimes: dict[str, float] = {}  # lowercase name -> last known mtime
        self._reload_locks: dict[str, asyncio.Lock] = {}  # per-key reload lock
        self._active: str | None = None
        self._modified: set[str] = set()

    def _get_mtime(self, path: str) -> float:
        """Get the modification time for a soul path (file or directory)."""
        p = Path(path)
        try:
            if p.is_file():
                return p.stat().st_mtime
            elif p.is_dir():
                soul_json = p / "soul.json"
                if soul_json.exists():
                    return soul_json.stat().st_mtime
            return 0.0
        except OSError:
            return 0.0

    def register(self, soul: Soul, path: str, fmt: str) -> None:
        """Register a soul. First registered becomes active."""
        key = soul.name.lower()
        self._souls[key] = soul
        self._paths[key] = path
        self._formats[key] = fmt
        self._mtimes[key] = self._get_mtime(path)
        self._reload_locks[key] = asyncio.Lock()
        if self._active is None:
            self._active = key

    def get(self, name: str | None = None) -> Soul:
        """Get a soul by name, or the active soul if name is None."""
        if name:
            key = name.lower()
            if key not in self._souls:
                available = ", ".join(s.name for s in self._souls.values())
                raise RuntimeError(f"No soul named '{name}'. Available: {available or '(none)'}")
            return self._souls[key]
        if self._active and self._active in self._souls:
            return self._souls[self._active]
        if len(self._souls) == 1:
            return next(iter(self._souls.values()))
        if not self._souls:
            raise RuntimeError(
                "No soul loaded. Call soul_birth first or set SOUL_PATH/SOUL_DIR env var."
            )
        available = ", ".join(s.name for s in self._souls.values())
        raise RuntimeError(
            f"Multiple souls loaded. Specify which with the 'soul' parameter. "
            f"Available: {available}"
        )

    def mark_modified(self, name: str | None = None) -> None:
        """Mark a soul as needing save on shutdown."""
        if name:
            key = name.lower()
        elif self._active:
            key = self._active
        else:
            return
        if key in self._souls:
            self._modified.add(key)

    def switch(self, name: str) -> Soul:
        """Set the active soul by name."""
        key = name.lower()
        if key not in self._souls:
            available = ", ".join(s.name for s in self._souls.values())
            raise RuntimeError(f"No soul named '{name}'. Available: {available or '(none)'}")
        self._active = key
        return self._souls[key]

    @property
    def active_soul(self) -> Soul | None:
        """The currently active soul, or None."""
        if self._active and self._active in self._souls:
            return self._souls[self._active]
        return None

    @property
    def names(self) -> list[str]:
        """Display names of all loaded souls."""
        return [s.name for s in self._souls.values()]

    @property
    def modified_entries(self) -> list[tuple[Soul, str, str]]:
        """(soul, path, format) for each modified soul."""
        return [
            (self._souls[n], self._paths[n], self._formats[n])
            for n in self._modified
            if n in self._souls and self._paths.get(n)
        ]

    async def check_and_reload(self, key: str) -> None:
        """Reload a soul from disk if its file was modified externally.

        Uses a per-key lock to prevent concurrent reloads of the same soul
        (e.g. background watcher and tool call racing).
        """
        path = self._paths.get(key)
        if not path:
            return
        lock = self._reload_locks.get(key)
        if not lock:
            return
        async with lock:
            current_mtime = self._get_mtime(path)
            if current_mtime <= self._mtimes.get(key, 0.0):
                return  # already up-to-date (or reloaded by another caller)
            try:
                reloaded = await Soul.awaken(path)
                self._souls[key] = reloaded
                self._mtimes[key] = current_mtime
                self._modified.discard(key)
                print(
                    f"soul-mcp: auto-reloaded {reloaded.name} (file changed on disk)",
                    file=sys.stderr,
                    flush=True,
                )
            except (FileNotFoundError, ValueError, SoulProtocolError) as e:
                print(
                    f"soul-mcp: auto-reload failed for {key}: {e}",
                    file=sys.stderr,
                    flush=True,
                )

    def clear(self) -> None:
        """Reset all state."""
        self._souls.clear()
        self._paths.clear()
        self._formats.clear()
        self._mtimes.clear()
        self._reload_locks.clear()
        self._active = None
        self._modified.clear()

    def __len__(self) -> int:
        return len(self._souls)

    def __bool__(self) -> bool:
        return len(self._souls) > 0


_registry = SoulRegistry()

# ── LCM Context instances (per-soul, keyed by lowercase soul name) ──
_contexts: dict[str, LCMContext] = {}


async def _get_or_create_context(soul_name: str) -> LCMContext:
    """Return (or create) the LCMContext for a soul. Uses in-memory SQLite."""
    key = soul_name.lower()
    if key not in _contexts:
        ctx = LCMContext(db_path=":memory:", engine=_engine)
        await ctx.initialize()
        _contexts[key] = ctx
        print(f"soul-mcp: LCM context initialized for {soul_name}", file=sys.stderr, flush=True)
    return _contexts[key]


# ── MCPSamplingEngine cache ──
# Lazily constructed on the first tool call that carries a FastMCP Context.
# Reused across all subsequent calls within the session.
_engine: MCPSamplingEngine | None = None


def _get_or_create_engine(ctx: Context) -> MCPSamplingEngine:
    """Return (or create) the session-scoped MCPSamplingEngine.

    Called from tool handlers that receive a FastMCP ``ctx``. Creates the engine
    once on first use and caches it at module level. All loaded souls are updated
    via ``Soul.set_engine()`` when the engine is first created so that cognitive
    operations (observe, reflect) benefit from host LLM sampling going forward.

    Args:
        ctx: FastMCP Context injected into the tool handler.

    Returns:
        The cached MCPSamplingEngine instance.
    """
    global _engine
    if _engine is None:
        _engine = MCPSamplingEngine(ctx)
        # Wire the engine into every loaded soul
        for soul in _registry._souls.values():
            soul.set_engine(_engine)
        # Wire the engine into any existing LCM contexts (for Level 1/2 compaction)
        for lcm_ctx in _contexts.values():
            lcm_ctx._compactor._engine = _engine
        print(
            "soul-mcp: MCPSamplingEngine wired — cognitive tasks routed to host LLM",
            file=sys.stderr,
            flush=True,
        )
    return _engine


# ── Helpers ──


async def _auto_save_one(soul: Soul, path: str, fmt: str) -> None:
    """Save a single soul to the appropriate format."""
    p = Path(path)
    if fmt == "zip" or p.suffix == ".soul":
        await soul.export(str(p))
    else:
        await soul.save_local(str(p))


async def _scan_soul_dir(directory: str) -> list[tuple[Soul, str, str]]:
    """Scan a directory for souls (subdirs with soul.json + .soul files)."""
    entries: list[tuple[Soul, str, str]] = []
    d = Path(directory)
    if not d.is_dir():
        return entries

    for item in sorted(d.iterdir()):
        try:
            if item.is_dir() and (item / "soul.json").exists():
                soul = await Soul.awaken(str(item))
                entries.append((soul, str(item), "directory"))
            elif item.is_file() and item.suffix == ".soul":
                soul = await Soul.awaken(str(item))
                entries.append((soul, str(item), "zip"))
        except (FileNotFoundError, ValueError, SoulProtocolError) as e:
            print(
                f"soul-mcp: skipping {item.name}: {e}",
                file=sys.stderr,
                flush=True,
            )
    return entries


# ── Background File Watcher ──


async def _file_watcher() -> None:
    """Background task: poll soul file mtimes and auto-reload on change.

    Runs every SOUL_POLL_INTERVAL seconds (default 2s, min 0.5s). When an
    external process (e.g. Claude Desktop) modifies the .soul file, the
    in-memory soul is replaced before the next tool call even happens.
    """
    while True:
        try:
            interval = max(0.5, float(os.environ.get("SOUL_POLL_INTERVAL", "2.0")))
        except (ValueError, TypeError):
            interval = 2.0
        await asyncio.sleep(interval)
        try:
            for key in list(_registry._souls):
                await _registry.check_and_reload(key)
        except Exception as e:
            print(
                f"soul-mcp: file watcher error: {e}",
                file=sys.stderr,
                flush=True,
            )


# ── Lifespan ──


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Load souls from SOUL_DIR or SOUL_PATH on startup, auto-save on shutdown."""
    global _registry, _engine
    _registry.clear()
    _engine = None  # reset engine cache so new sessions get a fresh MCPSamplingEngine

    soul_dir = os.environ.get("SOUL_DIR")
    soul_path = os.environ.get("SOUL_PATH")

    # Auto-detect: if no env vars set, look for .soul/ in CWD then ~/.soul/
    # Uses CWD (not __file__) so it works for all install modes (editable, wheel, uvx)
    if not soul_dir and not soul_path:
        _cwd_dir = Path.cwd() / ".soul"
        if _cwd_dir.is_dir() and any(_cwd_dir.iterdir()):
            soul_dir = str(_cwd_dir)
        elif _cwd_dir.is_dir():
            print(
                f"soul-mcp: .soul/ found at {_cwd_dir} but is empty, checking ~/.soul/",
                file=sys.stderr,
                flush=True,
            )
        # Fallback: ~/.soul/ as a user-level default
        if not soul_dir:
            _home_dir = Path.home() / ".soul"
            if _home_dir.is_dir() and any(_home_dir.iterdir()):
                soul_dir = str(_home_dir)

    print(
        f"soul-mcp: env SOUL_DIR={soul_dir!r} SOUL_PATH={soul_path!r}", file=sys.stderr, flush=True
    )

    if soul_dir:
        # Multi-soul: scan directory
        entries = await _scan_soul_dir(soul_dir)
        for soul, path, fmt in entries:
            _registry.register(soul, path, fmt)
        if entries:
            names = ", ".join(s.name for s, _, _ in entries)
            print(
                f"soul-mcp: loaded {len(entries)} soul(s): {names}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                f"soul-mcp: no souls found in SOUL_DIR={soul_dir!r}",
                file=sys.stderr,
                flush=True,
            )
    elif soul_path:
        # Single soul (backward compat)
        try:
            soul = await Soul.awaken(soul_path)
            fmt = "zip" if Path(soul_path).suffix == ".soul" else "directory"
            _registry.register(soul, soul_path, fmt)
        except (FileNotFoundError, ValueError, SoulProtocolError) as e:
            print(
                f"soul-mcp: failed to load SOUL_PATH={soul_path!r}: {e}",
                file=sys.stderr,
                flush=True,
            )
            print(
                "soul-mcp: starting without a soul. Call soul_birth to create one.",
                file=sys.stderr,
                flush=True,
            )

    # Start background file watcher
    watcher_task = asyncio.create_task(_file_watcher())

    yield

    # Stop file watcher
    watcher_task.cancel()
    try:
        await watcher_task
    except asyncio.CancelledError:
        pass

    # Auto-save modified souls on shutdown
    for soul, path, fmt in _registry.modified_entries:
        try:
            await _auto_save_one(soul, path, fmt)
            print(
                f"soul-mcp: auto-saved {soul.name} to {path}",
                file=sys.stderr,
                flush=True,
            )
        except Exception as e:
            print(
                f"soul-mcp: auto-save failed for {soul.name}: {e}",
                file=sys.stderr,
                flush=True,
            )

    # Close LCM contexts
    for lcm_ctx in _contexts.values():
        try:
            await lcm_ctx.close()
        except Exception:
            pass
    _contexts.clear()

    _registry.clear()
    _engine = None


mcp = FastMCP(
    "soul-protocol",
    instructions=(
        "Soul Protocol MCP server. Provides persistent AI identity"
        " and memory. Supports multiple souls via SOUL_DIR."
    ),
    lifespan=_lifespan,
)


async def _resolve_soul(soul: str | None = None) -> Soul:
    """Resolve a soul by name, or return the active soul. Auto-reloads if file changed."""
    s = _registry.get(soul)
    key = s.name.lower()
    await _registry.check_and_reload(key)
    # Re-fetch in case reload replaced the instance
    return _registry.get(soul)


def _validate_memory_type(memory_type: str) -> MemoryType:
    """Validate and convert memory type string, with helpful errors."""
    valid = [m.value for m in MemoryType if m != MemoryType.CORE]
    if memory_type == "core":
        raise ValueError(
            "Cannot store core memories via soul_remember."
            " Use soul.edit_core_memory() or the core memory"
            " resource instead."
            f" Valid types: {', '.join(valid)}"
        )
    try:
        return MemoryType(memory_type)
    except ValueError:
        raise ValueError(f"Invalid memory_type '{memory_type}'. Valid types: {', '.join(valid)}")


def _validate_mood(mood: str) -> Mood:
    """Validate and convert mood string, with helpful errors."""
    try:
        return Mood(mood)
    except ValueError:
        valid = ", ".join(m.value for m in Mood)
        raise ValueError(f"Invalid mood '{mood}'. Valid: {valid}")


# --- Tools (12) ---


@mcp.tool
async def soul_birth(
    name: str,
    archetype: str = "",
    values: list[str] | None = None,
    ctx: Context | None = None,
) -> str:
    """Create a new soul with persistent identity and memory.

    Args:
        name: The soul's name
        archetype: Optional archetype (e.g. "The Compassionate Creator")
        values: Optional list of core values
    """
    soul = await Soul.birth(
        name,
        archetype=archetype,
        values=values or [],
    )
    _registry.register(soul, "", "directory")
    _registry.switch(name)
    # Wire MCPSamplingEngine if a host context is available
    if ctx is not None:
        engine = _get_or_create_engine(ctx)
        soul.set_engine(engine)
    result: dict[str, Any] = {
        "name": soul.name,
        "did": soul.did,
        "status": "born",
        "active": True,
    }
    if len(_registry) > 1:
        result["info"] = f"Soul added. {len(_registry)} souls now loaded."
    return json.dumps(result)


@mcp.tool
async def soul_list() -> str:
    """List all loaded souls with their name, DID, memory count, and active status."""
    souls = []
    for key, s in _registry._souls.items():
        souls.append(
            {
                "name": s.name,
                "did": s.did,
                "memories": s.memory_count,
                "active": key == _registry._active,
                "format": _registry._formats.get(key, "unknown"),
                "path": _registry._paths.get(key, ""),
            }
        )
    return json.dumps({"count": len(souls), "souls": souls})


@mcp.tool
async def soul_switch(name: str) -> str:
    """Set the active soul by name.

    Args:
        name: Name of the soul to activate (case-insensitive)
    """
    soul = _registry.switch(name)
    s = soul.state
    return json.dumps(
        {
            "status": "switched",
            "name": soul.name,
            "did": soul.did,
            "mood": s.mood.value,
            "energy": round(s.energy, 1),
        }
    )


@mcp.tool
async def soul_observe(
    user_input: str,
    agent_output: str,
    channel: str = "mcp",
    soul: str | None = None,
    user_id: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Process an interaction through the psychology pipeline.
    Extracts facts, detects sentiment, updates self-model.
    When called from Claude Code / Claude Desktop, uses the host LLM for
    richer cognitive processing via MCP sampling (no extra API key needed).

    Args:
        user_input: What the user said
        agent_output: What the agent responded
        channel: Source channel identifier
        soul: Target soul name (uses active soul if omitted)
        user_id: When set, attribute the observed memory to this user_id
            (multi-user souls, #46). Per-user bond is strengthened instead
            of the default bond.
    """
    if ctx is not None:
        _get_or_create_engine(ctx)
    s = await _resolve_soul(soul)
    await s.observe(
        Interaction(
            user_input=user_input,
            agent_output=agent_output,
            channel=channel,
        ),
        user_id=user_id,
    )
    _registry.mark_modified(soul)
    state = s.state
    return json.dumps(
        {
            "status": "observed",
            "soul": s.name,
            "mood": state.mood.value,
            "energy": round(state.energy, 1),
            "user_id": user_id,
        }
    )


@mcp.tool
async def soul_remember(
    content: str,
    importance: int = 5,
    memory_type: str = "semantic",
    emotion: str | None = None,
    soul: str | None = None,
    domain: str = "default",
) -> str:
    """Store a memory directly.

    Args:
        content: The memory content
        importance: 1-10 scale
        memory_type: One of: episodic, semantic, procedural, social
        emotion: Optional emotion label
        soul: Target soul name (uses active soul if omitted)
        domain: Sub-namespace inside the layer (#41). Defaults to "default".
            Use values like "finance" or "legal" to scope memories.
    """
    s = await _resolve_soul(soul)
    mt = _validate_memory_type(memory_type)
    importance = max(1, min(10, importance))
    memory_id = await s.remember(
        content,
        type=mt,
        importance=importance,
        emotion=emotion,
        domain=domain,
    )
    _registry.mark_modified(soul)
    return json.dumps(
        {
            "memory_id": memory_id,
            "soul": s.name,
            "type": memory_type,
            "domain": domain,
            "importance": importance,
        }
    )


@mcp.tool
async def soul_recall(
    query: str,
    limit: int = 5,
    soul: str | None = None,
    user_id: str | None = None,
    layer: str | None = None,
    domain: str | None = None,
) -> str:
    """Search the soul's memories by natural language query.

    Args:
        query: Search query
        limit: Maximum results to return
        soul: Target soul name (uses active soul if omitted)
        user_id: When set, restrict results to memories attributed to this
            user_id, plus legacy entries with no user_id (multi-user souls,
            #46). When unset, returns all memories regardless of attribution.
        layer: When set, restrict recall to a single layer (#41). Accepts
            built-in names (episodic, semantic, procedural, social) or any
            custom layer name.
        domain: When set, restrict recall to a single domain sub-namespace
            (#41), e.g. "finance" or "legal".
    """
    s = await _resolve_soul(soul)
    results = await s.recall(query, limit=limit, user_id=user_id, layer=layer, domain=domain)
    memories = [
        {
            "id": r.id,
            "type": r.type.value,
            "layer": r.layer or r.type.value,
            "domain": r.domain or "default",
            "content": r.content,
            "importance": r.importance,
            "emotion": r.emotion,
            "user_id": r.user_id,
        }
        for r in results
    ]
    return json.dumps({"count": len(memories), "soul": s.name, "memories": memories})


@mcp.tool
async def soul_reflect(
    soul: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Trigger memory reflection and consolidation.
    Identifies themes, summarizes patterns, generates self-insights.
    Uses the host LLM via MCP sampling when running inside Claude Code /
    Claude Desktop — no extra API key needed.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    if ctx is not None:
        _get_or_create_engine(ctx)
    s = await _resolve_soul(soul)
    result = await s.reflect()
    if result is None:
        return json.dumps(
            {
                "status": "skipped",
                "soul": s.name,
                "reason": "No CognitiveEngine available for reflection",
            }
        )
    return json.dumps(
        {
            "status": "reflected",
            "soul": s.name,
            "themes": result.themes,
            "emotional_patterns": result.emotional_patterns,
            "self_insight": result.self_insight,
        }
    )


@mcp.tool
async def soul_dream(
    soul: str | None = None,
    since: str | None = None,
) -> str:
    """Run an offline dream cycle — batch memory consolidation.

    Dreaming reviews accumulated episodes to detect topic patterns,
    extract recurring procedures, consolidate the knowledge graph,
    and propose personality evolution from behavioral trends.

    Unlike reflect (which only summarizes), dream performs cross-tier
    synthesis: episodes → procedures, entities → evolution.

    Args:
        soul: Target soul name (uses active soul if omitted)
        since: ISO datetime — only review episodes after this time (optional)
    """
    import dataclasses
    from datetime import datetime as dt

    s = await _resolve_soul(soul)
    # Strip tzinfo — episodic store uses naive datetimes
    since_dt = dt.fromisoformat(since).replace(tzinfo=None) if since else None
    report = await s.dream(since=since_dt)
    _registry.mark_modified(soul)

    def _ser(obj):
        if isinstance(obj, dt):
            return obj.isoformat()
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return str(obj)

    return json.dumps(dataclasses.asdict(report), default=_ser)


@mcp.tool
async def soul_state(soul: str | None = None) -> str:
    """Get the soul's current mood, energy, focus, and social battery.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    s.recompute_focus()
    st = s.state
    return json.dumps(
        {
            "soul": s.name,
            "mood": st.mood.value,
            "energy": round(st.energy, 1),
            "focus": st.focus,
            "social_battery": round(st.social_battery, 1),
            "lifecycle": s.lifecycle.value,
        }
    )


@mcp.tool
async def soul_feel(
    mood: str | None = None,
    energy: float | None = None,
    focus: str | None = None,
    soul: str | None = None,
) -> str:
    """Update the soul's emotional state.

    Args:
        mood: One of: neutral, curious, focused, tired, excited,
              contemplative, satisfied, concerned
        energy: Energy delta (-100 to 100). Positive increases,
                negative decreases. Clamped to 0-100.
        focus: Lock focus to one of low/medium/high/max, or 'auto'
                to clear the lock and re-enable density-driven focus.
        soul: Target soul name (uses active soul if omitted)
    """
    from soul_protocol.runtime.types import FOCUS_LEVELS

    s = await _resolve_soul(soul)
    kwargs: dict[str, Any] = {}
    if mood is not None:
        kwargs["mood"] = _validate_mood(mood)
    if energy is not None:
        energy = max(-100.0, min(100.0, energy))
        kwargs["energy"] = energy
    if focus is not None:
        if focus != "auto" and focus not in FOCUS_LEVELS:
            valid = ", ".join(FOCUS_LEVELS) + ", auto"
            raise ValueError(f"Invalid focus '{focus}'. Valid: {valid}")
        kwargs["focus"] = focus
    s.feel(**kwargs)
    s.recompute_focus()
    _registry.mark_modified(soul)
    st = s.state
    return json.dumps(
        {
            "soul": s.name,
            "mood": st.mood.value,
            "energy": round(st.energy, 1),
            "focus": st.focus,
            "focus_override": st.focus_override,
        }
    )


@mcp.tool
async def soul_prompt(soul: str | None = None) -> str:
    """Generate the complete system prompt for LLM injection.
    Includes DNA, identity, core memory, current state, and self-model.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    return s.to_system_prompt()


@mcp.tool
async def soul_save(
    path: str | None = None,
    soul: str | None = None,
) -> str:
    """Persist the soul to disk.

    Args:
        path: Directory or file path. If omitted, saves to the
              original SOUL_PATH or ~/.soul/<soul_id>/.
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    key = (soul or "").lower() if soul else _registry._active
    save_path = path or (key and _registry._paths.get(key, "")) or None
    fmt = (key and _registry._formats.get(key, "directory")) or "directory"

    if save_path:
        await _auto_save_one(s, save_path, fmt)
        if key and key in _registry._paths:
            _registry._paths[key] = save_path
        if key:
            _registry._mtimes[key] = _registry._get_mtime(save_path)
    else:
        await s.save()
        save_path = str(Path.home() / ".soul" / s.did)

    return json.dumps(
        {
            "status": "saved",
            "path": save_path,
            "name": s.name,
        }
    )


@mcp.tool
async def soul_export(
    path: str,
    soul: str | None = None,
) -> str:
    """Export the soul as a portable .soul file (zip archive).
    Contains identity, memory, state, and self-model.

    Args:
        path: Output file path (must end in .soul)
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    resolved = Path(path).resolve()
    if resolved.suffix != ".soul":
        raise ValueError(f"Export path must end in .soul, got: {path!r}")
    if not resolved.parent.exists():
        raise ValueError(f"Parent directory does not exist: {resolved.parent}")
    await s.export(resolved)
    return json.dumps(
        {
            "status": "exported",
            "path": str(resolved),
            "name": s.name,
        }
    )


@mcp.tool
async def soul_reload(
    soul: str | None = None,
) -> str:
    """Reload a soul from disk, picking up any changes made externally.

    Use this when the .soul file has been updated outside the MCP server
    (e.g. by another process, a different session, or manual editing).
    The in-memory soul is replaced with the freshly loaded version.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    key = s.name.lower()
    source_path = _registry._paths.get(key)
    if not source_path:
        raise RuntimeError(
            f"No source path for soul '{s.name}'. "
            "Cannot reload a soul that was created at runtime (not loaded from disk)."
        )
    fmt = _registry._formats.get(key, "directory")

    reloaded = await Soul.awaken(source_path)
    _registry._souls[key] = reloaded
    _registry._mtimes[key] = _registry._get_mtime(source_path)
    # Preserve active status and path — just swap the Soul instance
    _registry._modified.discard(key)

    return json.dumps(
        {
            "status": "reloaded",
            "name": reloaded.name,
            "path": source_path,
            "format": fmt,
            "memories": reloaded.memory_count,
        }
    )


# --- Psychology Pipeline Tools (v0.2.7) ---


@mcp.tool
async def soul_skills(soul: str | None = None) -> str:
    """View the soul's learned skills with level, XP, and progress.

    Skills are learned from entity extraction during observe() and from
    evaluation-based XP grants. They persist across sessions.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    skills = s.skills.skills
    if not skills:
        return json.dumps({"soul": s.name, "skills": [], "total": 0})
    return json.dumps(
        {
            "soul": s.name,
            "total": len(skills),
            "skills": [
                {
                    "id": sk.id,
                    "name": sk.name,
                    "level": sk.level,
                    "xp": sk.xp,
                    "xp_to_next": sk.xp_to_next,
                }
                for sk in sorted(skills, key=lambda x: x.xp, reverse=True)
            ],
        }
    )


@mcp.tool
async def soul_evaluate(
    user_input: str,
    agent_output: str,
    domain: str | None = None,
    soul: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Evaluate an interaction against a rubric and build evaluation history.

    Scores the interaction on completeness, relevance, helpfulness, and
    specificity. Stores learning as procedural memory and grants skill XP.
    Evaluation history feeds the evolution trigger system.

    Args:
        user_input: What the user said
        agent_output: What the agent responded
        domain: Self-model domain for rubric selection (auto-detected if omitted)
        soul: Target soul name (uses active soul if omitted)
    """
    if ctx is not None:
        _get_or_create_engine(ctx)
    s = await _resolve_soul(soul)
    interaction = Interaction(user_input=user_input, agent_output=agent_output)
    result = await s.evaluate(interaction, domain=domain)
    _registry.mark_modified(soul)
    return json.dumps(
        {
            "soul": s.name,
            "rubric": result.rubric_id,
            "overall_score": round(result.overall_score, 3),
            "criteria": [
                {"name": cr.criterion, "score": round(cr.score, 3), "passed": cr.passed}
                for cr in result.criterion_results
            ],
            "learning": result.learning,
            "eval_history_size": len(s.evaluator._history),
        }
    )


@mcp.tool
async def soul_learn(
    user_input: str,
    agent_output: str,
    domain: str | None = None,
    soul: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Evaluate an interaction and create a learning event if notable.

    Combines evaluation with learning event creation. High-scoring
    interactions generate success patterns; low-scoring ones generate
    failure patterns. Both are stored as procedural memory.

    Args:
        user_input: What the user said
        agent_output: What the agent responded
        domain: Domain for rubric selection (auto-detected if omitted)
        soul: Target soul name (uses active soul if omitted)
    """
    if ctx is not None:
        _get_or_create_engine(ctx)
    s = await _resolve_soul(soul)
    interaction = Interaction(user_input=user_input, agent_output=agent_output)
    event = await s.learn(interaction, domain=domain)
    _registry.mark_modified(soul)
    if event is None:
        return json.dumps(
            {
                "soul": s.name,
                "learning_event": None,
                "reason": "Score in medium range — no notable learning pattern",
            }
        )
    return json.dumps(
        {
            "soul": s.name,
            "learning_event": {
                "id": event.id,
                "lesson": event.lesson,
                "domain": event.domain,
                "score": round(event.evaluation_score, 3) if event.evaluation_score else None,
                "confidence": round(event.confidence, 3),
                "skill_id": event.skill_id,
            },
        }
    )


@mcp.tool
async def soul_evolve(
    action: str = "list",
    trait: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    mutation_id: str | None = None,
    soul: str | None = None,
) -> str:
    """Manage soul evolution — propose, approve, reject, or list mutations.

    Evolution allows the soul's traits to change over time based on
    interaction patterns. Mutations can be proposed manually or triggered
    automatically by evaluation streaks.

    Args:
        action: One of: list, propose, approve, reject
        trait: Trait path to mutate (e.g. "communication.warmth") — for propose
        new_value: New value for the trait — for propose
        reason: Why this mutation is proposed — for propose
        mutation_id: ID of mutation to approve/reject — for approve/reject
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)

    if action == "list":
        pending = s.pending_mutations
        history = s.evolution_history
        return json.dumps(
            {
                "soul": s.name,
                "pending": [
                    {
                        "id": m.id,
                        "trait": m.trait,
                        "old": m.old_value,
                        "new": m.new_value,
                        "reason": m.reason,
                    }
                    for m in pending
                ],
                "history_count": len(history),
            }
        )

    elif action == "propose":
        if not trait or not new_value or not reason:
            return json.dumps({"error": "propose requires trait, new_value, and reason"})
        mutation = await s.propose_evolution(
            trait=trait,
            new_value=new_value,
            reason=reason,
        )
        _registry.mark_modified(soul)
        return json.dumps(
            {
                "soul": s.name,
                "mutation_id": mutation.id,
                "trait": mutation.trait,
                "old_value": mutation.old_value,
                "new_value": mutation.new_value,
                "status": "pending",
            }
        )

    elif action == "approve":
        if not mutation_id:
            return json.dumps({"error": "approve requires mutation_id"})
        success = await s.approve_evolution(mutation_id)
        _registry.mark_modified(soul)
        return json.dumps({"soul": s.name, "mutation_id": mutation_id, "approved": success})

    elif action == "reject":
        if not mutation_id:
            return json.dumps({"error": "reject requires mutation_id"})
        success = await s.reject_evolution(mutation_id)
        _registry.mark_modified(soul)
        return json.dumps({"soul": s.name, "mutation_id": mutation_id, "rejected": success})

    return json.dumps({"error": f"Unknown action: {action}. Use list/propose/approve/reject."})


@mcp.tool
async def soul_bond(
    strengthen: float | None = None,
    soul: str | None = None,
) -> str:
    """View or modify the soul's bond strength.

    Bond strength influences memory visibility — higher bond unlocks
    BONDED and PRIVATE memories. Bond grows naturally through observe()
    interactions, or can be manually adjusted.

    Args:
        strengthen: Amount to strengthen bond by (negative to weaken). Omit to just view.
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    bond = s.bond
    if strengthen is not None:
        if strengthen >= 0:
            bond.strengthen(amount=strengthen)
        else:
            bond.bond_strength = max(0.0, bond.bond_strength + strengthen)
        _registry.mark_modified(soul)
    return json.dumps(
        {
            "soul": s.name,
            "bond_strength": round(bond.bond_strength, 2),
            "interaction_count": bond.interaction_count,
        }
    )


# --- Maintenance Tools (v0.2.8) ---


@mcp.tool
async def soul_forget(
    query: str,
    confirm: bool = False,
    soul: str | None = None,
) -> str:
    """Delete memories matching a query (GDPR-compliant).

    Searches across all memory tiers (episodic, semantic, procedural) and
    deletes matching entries. Records a deletion audit entry without storing
    deleted content.

    Args:
        query: Search query to match against memory content
        confirm: Must be true to actually delete (safety gate)
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    if not confirm:
        # Dry-run: search but don't delete
        results = await s.recall(query, limit=50)
        return json.dumps(
            {
                "status": "preview",
                "soul": s.name,
                "query": query,
                "matching_count": len(results),
                "hint": "Set confirm=true to delete these memories",
            }
        )
    result = await s.forget(query)
    _registry.mark_modified(soul)
    return json.dumps(
        {
            "status": "deleted",
            "soul": s.name,
            "query": query,
            "total_deleted": result.get("total_deleted", 0),
            "tiers": result.get("tiers", {}),
        }
    )


@mcp.tool
async def soul_edit_core(
    persona: str | None = None,
    human: str | None = None,
    soul: str | None = None,
) -> str:
    """Update the soul's core memory (always-loaded persona and human knowledge).

    Core memory is never evicted — it persists across every interaction.
    Use persona for the soul's self-description and human for knowledge
    about the bonded human.

    Args:
        persona: New persona text (soul's self-description). Omit to keep current.
        human: New human knowledge text. Omit to keep current.
        soul: Target soul name (uses active soul if omitted)
    """
    s = await _resolve_soul(soul)
    if persona is None and human is None:
        core = s.get_core_memory()
        return json.dumps(
            {
                "soul": s.name,
                "persona": core.persona,
                "human": core.human,
                "hint": "Provide persona and/or human to update",
            }
        )
    await s.edit_core_memory(persona=persona, human=human)
    _registry.mark_modified(soul)
    core = s.get_core_memory()
    return json.dumps(
        {
            "status": "updated",
            "soul": s.name,
            "persona": core.persona,
            "human": core.human,
        }
    )


@mcp.tool
async def soul_health(
    soul: str | None = None,
) -> str:
    """Run a health audit on the soul's memory, skills, bond, and graph.

    Returns counts for each memory tier, detects duplicates, orphan graph
    nodes, bond/skill anomalies, and low-importance memory buildup.

    Args:
        soul: Target soul name (uses active soul if omitted)
    """
    import builtins as _builtins

    from ..runtime.memory.compression import MemoryCompressor

    s = await _resolve_soul(soul)
    mm = s._memory

    episodic = _builtins.list(mm._episodic.entries())
    semantic = _builtins.list(mm._semantic.facts())
    procedural = _builtins.list(mm._procedural.entries())
    graph_nodes = mm._graph.entities()
    skills = s.skills.skills
    evals = s.evaluator._history
    total = len(episodic) + len(semantic) + len(procedural)

    # Detect duplicates
    compressor = MemoryCompressor()
    all_mems = episodic + semantic + procedural
    deduped = compressor.deduplicate(all_mems, similarity_threshold=0.8)
    dup_count = len(all_mems) - len(deduped)

    # Low-importance
    low_imp = [m for m in all_mems if m.importance <= 2]

    # Stale eval procedurals
    stale_proc = [p for p in procedural if p.content.startswith("Scored ")]

    # Orphan graph nodes
    all_content = " ".join(m.content for m in all_mems)
    orphan_nodes = [n for n in graph_nodes if n.lower() not in all_content.lower() and len(n) > 2]

    # Bond sanity
    bond = s.bond
    bond_issues = []
    if bond.bond_strength > 100:
        bond_issues.append(f"Bond strength {bond.bond_strength:.0f} exceeds 100")
    if bond.bond_strength < 0:
        bond_issues.append(f"Bond strength {bond.bond_strength:.0f} is negative")

    # Skill sanity
    skill_issues = []
    for sk in skills:
        if sk.xp < 0:
            skill_issues.append(f"Skill {sk.id} has negative XP ({sk.xp})")
        if sk.level < 1 or sk.level > 10:
            skill_issues.append(f"Skill {sk.id} has invalid level ({sk.level})")

    issues = bond_issues + skill_issues
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate memories (>80% overlap)")
    if len(orphan_nodes) > 10:
        issues.append(f"{len(orphan_nodes)} orphan graph nodes")

    return json.dumps(
        {
            "soul": s.name,
            "tiers": {
                "episodic": len(episodic),
                "semantic": len(semantic),
                "procedural": len(procedural),
                "total": total,
            },
            "graph_nodes": len(graph_nodes),
            "skills": len(skills),
            "eval_history": len(evals),
            "bond_strength": round(bond.bond_strength, 2),
            "duplicates": dup_count,
            "low_importance": len(low_imp),
            "stale_evals": len(stale_proc),
            "orphan_nodes": len(orphan_nodes),
            "issues": issues,
            "healthy": len(issues) == 0,
        }
    )


@mcp.tool
async def soul_cleanup(
    dry_run: bool = True,
    soul: str | None = None,
) -> str:
    """Run cleanup on the soul — deduplicate memories and remove stale evals.

    Identifies near-duplicate memories (>80% overlap) across all tiers and
    removes stale evaluation procedural entries. Use dry_run=true (default)
    to preview what would be cleaned.

    Args:
        dry_run: If true, report what would be cleaned without changing anything
        soul: Target soul name (uses active soul if omitted)
    """
    import builtins as _builtins

    from ..runtime.memory.compression import MemoryCompressor

    s = await _resolve_soul(soul)
    mm = s._memory
    actions: list[tuple[str, str, set]] = []

    # 1. Deduplicate
    compressor = MemoryCompressor()
    for tier_name, store in [
        ("episodic", mm._episodic),
        ("semantic", mm._semantic),
        ("procedural", mm._procedural),
    ]:
        if tier_name == "semantic":
            entries = _builtins.list(store.facts())
        else:
            entries = _builtins.list(store.entries())
        if not entries:
            continue
        deduped = compressor.deduplicate(entries, similarity_threshold=0.8)
        removed_ids = {m.id for m in entries} - {m.id for m in deduped}
        if removed_ids:
            actions.append(("dedup", tier_name, removed_ids))

    # 2. Stale evaluation procedurals
    procedural = _builtins.list(mm._procedural.entries())
    stale = [p for p in procedural if p.content.startswith("Scored ") and p.importance <= 5]
    if stale:
        actions.append(("stale_evals", "procedural", {p.id for p in stale}))

    # Build summary
    summary: list[dict[str, Any]] = []
    total_items = 0
    for action_type, target, items in actions:
        total_items += len(items)
        summary.append(
            {
                "action": action_type,
                "tier": target,
                "count": len(items),
            }
        )

    if dry_run or not actions:
        return json.dumps(
            {
                "status": "dry_run" if actions else "clean",
                "soul": s.name,
                "total_items": total_items,
                "actions": summary,
            }
        )

    # Execute cleanup
    removed = 0
    for action_type, target, items in actions:
        for mid in items:
            if target == "episodic":
                await mm._episodic.remove(mid)
            elif target == "semantic":
                await mm._semantic.remove(mid)
            elif target == "procedural":
                await mm._procedural.remove(mid)
            removed += 1

    _registry.mark_modified(soul)
    return json.dumps(
        {
            "status": "cleaned",
            "soul": s.name,
            "removed": removed,
            "actions": summary,
        }
    )


# --- Context Tools (LCM — Lossless Context Management) ---


@mcp.tool
async def soul_context_ingest(
    role: str,
    content: str,
    soul: str | None = None,
) -> str:
    """Ingest a message into the soul's context store.

    Messages are immutable once stored — the store never updates or deletes them.
    Compaction runs automatically when the token budget is approached.

    Args:
        role: Message role (e.g., "user", "assistant", "system").
        content: Message content text.
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    ctx = await _get_or_create_context(s.name)
    msg_id = await ctx.ingest(role, content)
    desc = await ctx.describe()
    return json.dumps(
        {
            "message_id": msg_id,
            "soul": s.name,
            "total_messages": desc.total_messages,
            "total_tokens": desc.total_tokens,
        }
    )


@mcp.tool
async def soul_context_assemble(
    max_tokens: int = 100_000,
    system_reserve: int = 0,
    soul: str | None = None,
) -> str:
    """Assemble a context window that fits within the token budget.

    Returns ordered nodes (verbatim + compacted) ready for LLM injection.
    Applies three-level compaction as needed: Summary (LLM), Bullets (LLM),
    Truncation (deterministic, guaranteed convergence).

    Args:
        max_tokens: Token budget for the assembled context.
        system_reserve: Tokens to reserve for system prompts / tool schemas.
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    ctx = await _get_or_create_context(s.name)
    result = await ctx.assemble(max_tokens, system_reserve=system_reserve)
    return json.dumps(
        {
            "soul": s.name,
            "node_count": len(result.nodes),
            "total_tokens": result.total_tokens,
            "compaction_applied": result.compaction_applied,
            "nodes": [
                {
                    "level": n.level.value,
                    "content": n.content,
                    "token_count": n.token_count,
                    "seq_range": [n.seq_start, n.seq_end],
                }
                for n in result.nodes
            ],
        }
    )


@mcp.tool
async def soul_context_grep(
    pattern: str,
    limit: int = 20,
    soul: str | None = None,
) -> str:
    """Search the soul's context history by regex pattern.

    Searches the immutable message store — even compacted messages are
    searchable since originals are never deleted.

    Args:
        pattern: Regex pattern to search for.
        limit: Maximum number of results.
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    ctx = await _get_or_create_context(s.name)
    hits = await ctx.grep(pattern, limit=limit)
    return json.dumps(
        {
            "soul": s.name,
            "count": len(hits),
            "results": [
                {
                    "message_id": h.message_id,
                    "seq": h.seq,
                    "role": h.role,
                    "snippet": h.content_snippet,
                }
                for h in hits
            ],
        }
    )


@mcp.tool
async def soul_context_expand(
    node_id: str,
    soul: str | None = None,
) -> str:
    """Expand a compacted node back to its original messages.

    Walks the DAG to recover verbatim content that was summarized or truncated.
    Nothing is ever truly lost — this is the "lossless" in Lossless Context Management.

    Args:
        node_id: The ID of the compacted node to expand.
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    ctx = await _get_or_create_context(s.name)
    result = await ctx.expand(node_id)
    return json.dumps(
        {
            "soul": s.name,
            "node_id": result.node_id,
            "level": result.level.value,
            "original_count": len(result.original_messages),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "seq": m.seq,
                }
                for m in result.original_messages
            ],
        }
    )


@mcp.tool
async def soul_context_describe(
    soul: str | None = None,
) -> str:
    """Get a metadata snapshot of the soul's context store.

    Returns message count, token totals, date range, and compaction statistics.

    Args:
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    ctx = await _get_or_create_context(s.name)
    desc = await ctx.describe()
    return json.dumps(
        {
            "soul": s.name,
            "total_messages": desc.total_messages,
            "total_nodes": desc.total_nodes,
            "total_tokens": desc.total_tokens,
            "compaction_stats": desc.compaction_stats,
            "date_range": [
                desc.date_range[0].isoformat() if desc.date_range[0] else None,
                desc.date_range[1].isoformat() if desc.date_range[1] else None,
            ],
        }
    )


# --- Trust chain tools (#42, 2 tools) ---


@mcp.tool
async def soul_verify(
    soul: str | None = None,
) -> str:
    """Verify the trust chain integrity for a soul.

    Returns JSON ``{soul, did, valid, length, signers, first_failure}``.
    The chain is the soul's append-only signed history of all
    audit-worthy actions (memory writes, supersedes, evolution events,
    learning events, bond changes). A chain that fails verification has
    been tampered with — never trust the soul's claimed history.

    Args:
        soul: Target soul name (uses active soul if omitted).
    """
    from soul_protocol.spec.trust import chain_integrity_check

    s = await _resolve_soul(soul)
    summary = chain_integrity_check(s.trust_chain)
    return json.dumps(
        {
            "soul": s.name,
            "did": s.did,
            "valid": summary["valid"],
            "length": summary["length"],
            "signers": list(summary["signers"]),
            "first_failure": summary["first_failure"],
        }
    )


@mcp.tool
async def soul_audit(
    action_prefix: str | None = None,
    limit: int | None = None,
    soul: str | None = None,
) -> str:
    """Return a human-readable timeline of signed actions on the soul's chain.

    Each row carries ``{seq, timestamp, action, actor_did, payload_hash, summary}``.
    The ``summary`` field (#201) is a short per-action human-readable
    description set at append time — pre-#201 entries return ``""``.
    Use ``action_prefix`` (e.g. ``"memory."``) to scope to one category.
    Use ``limit`` to take only the most recent N rows (tail behaviour).

    Args:
        action_prefix: Optional dot-namespaced prefix filter.
        limit: Optional cap on number of rows (most-recent-N).
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    log = s.audit_log(action_prefix=action_prefix, limit=limit)
    return json.dumps({"soul": s.name, "did": s.did, "entries": log})


@mcp.tool
async def soul_prune_chain(
    keep: int | None = None,
    apply: bool = False,
    reason: str = "manual",
    soul: str | None = None,
) -> str:
    """Compress old trust-chain history into a signed chain.pruned marker (#203).

    Touch-time stub for v0.5.0. Returns dry-run preview by default; pass
    ``apply=True`` to actually mutate the chain. Genesis (seq=0) is always
    preserved. The marker carries ``{count, low_seq, high_seq, reason}`` so
    an auditor can reconstruct what was dropped.

    Returns JSON ``{soul, did, applied, summary, chain_length, keep}``.
    ``summary`` is the prune summary (count/low_seq/high_seq/marker_seq).

    The full archival design (separate trust_chain/archive/ directory with
    checkpoint entries spanning archive files) is deferred to v0.5.x.

    Args:
        keep: Length threshold. When the chain has more than ``keep``
            entries, non-genesis history is compressed into a single marker.
            Defaults to the soul's Biorhythms.trust_chain_max_entries.
        apply: When False (default), return a dry-run preview only. When
            True, mutate the chain.
        reason: Free-form label written onto the marker payload.
        soul: Target soul name (uses active soul if omitted).
    """
    s = await _resolve_soul(soul)
    mgr = s.trust_chain_manager

    effective_keep = keep if keep is not None else mgr.max_entries
    if effective_keep is None or effective_keep <= 0:
        return json.dumps(
            {
                "soul": s.name,
                "did": s.did,
                "applied": False,
                "error": (
                    "no keep value provided and the soul's Biorhythms."
                    "trust_chain_max_entries is 0 (auto-prune disabled)"
                ),
            }
        )

    # Always preview first so we can avoid a mutation when there is
    # nothing to drop. Reporting applied=True for a no-op would confuse
    # auditors of the chain (no marker entry was actually written).
    preview = mgr.dry_run_prune(keep=effective_keep)
    if not apply or preview["count"] == 0:
        return json.dumps(
            {
                "soul": s.name,
                "did": s.did,
                "applied": False,
                "summary": preview,
                "chain_length": mgr.length,
                "keep": effective_keep,
            }
        )

    summary = mgr.prune(keep=effective_keep, reason=reason)
    # Mark the soul modified so the registry's auto-save persists the
    # mutated chain on shutdown. Tools that mutate state follow this
    # pattern (soul_observe, soul_remember, etc.).
    _registry.mark_modified(soul)
    return json.dumps(
        {
            "soul": s.name,
            "did": s.did,
            "applied": True,
            "summary": summary,
            "chain_length": mgr.length,
            "keep": effective_keep,
        }
    )


@mcp.tool
async def soul_eval(
    yaml_path: str | None = None,
    yaml_string: str | None = None,
    case_filter: str | None = None,
    soul: str | None = None,
) -> str:
    """Run a YAML eval spec against the active soul (#160).

    Unlike the CLI ``soul eval`` command — which births a fresh soul
    from the spec's ``seed`` block — this MCP tool runs against the
    soul that is already loaded so an agent can self-evaluate against
    its current state.

    Either ``yaml_path`` or ``yaml_string`` is required (not both):

    - ``yaml_path``: filesystem path to a YAML eval file.
    - ``yaml_string``: raw YAML text (handy when the agent generates
      its own eval cases programmatically).

    The ``seed`` block on the spec is intentionally ignored — the soul's
    live memories, OCEAN, bonds, and state are the seed. Only ``cases``
    run.

    Args:
        yaml_path: Path to a .yaml/.yml file (mutually exclusive with
            yaml_string).
        yaml_string: Raw YAML text.
        case_filter: Optional substring filter on case names.
        soul: Target soul name (uses active soul if omitted).

    Returns:
        JSON string with the EvalResult: spec_name, cases (each with
        name, passed, score, skipped, output, details), pass/fail/skip
        counts, and total duration_ms.
    """
    if (yaml_path is None) == (yaml_string is None):
        return json.dumps(
            {
                "error": "exactly one of yaml_path / yaml_string is required",
            }
        )

    from soul_protocol.eval import (  # lazy — keeps cold-start small
        load_eval_spec,
        parse_eval_spec,
        run_eval_against_soul,
    )

    if yaml_string is not None:
        try:
            import yaml as _yaml

            data = _yaml.safe_load(yaml_string)
            if not isinstance(data, dict):
                return json.dumps({"error": "yaml_string must contain a mapping at top level"})
            spec = parse_eval_spec(data)
        except Exception as e:
            return json.dumps({"error": f"failed to parse yaml_string: {e}"})
    else:
        try:
            spec = load_eval_spec(yaml_path)
        except Exception as e:
            return json.dumps({"error": f"failed to load {yaml_path}: {e}"})

    s = await _resolve_soul(soul)
    result = await run_eval_against_soul(spec, s, case_filter=case_filter)
    return json.dumps(result.model_dump(mode="json"))


# --- Resources (3) ---


@mcp.resource("soul://identity")
async def soul_identity_resource() -> str:
    """Full identity JSON (DID, name, archetype, values, origin)."""
    s = await _resolve_soul()
    identity = s.identity
    return json.dumps(
        {
            "did": identity.did,
            "name": identity.name,
            "archetype": identity.archetype,
            "born": identity.born.isoformat(),
            "bonded_to": identity.bonded_to,
            "core_values": identity.core_values,
            "origin_story": identity.origin_story,
        }
    )


@mcp.resource("soul://memory/core")
async def soul_core_memory_resource() -> str:
    """Core memory: persona definition and human knowledge."""
    s = await _resolve_soul()
    core = s.get_core_memory()
    return json.dumps(
        {
            "persona": core.persona,
            "human": core.human,
        }
    )


@mcp.resource("soul://state")
async def soul_state_resource() -> str:
    """Current soul state: mood, energy, focus, social battery."""
    s = await _resolve_soul()
    s.recompute_focus()
    st = s.state
    return json.dumps(
        {
            "mood": st.mood.value,
            "energy": round(st.energy, 1),
            "focus": st.focus,
            "social_battery": round(st.social_battery, 1),
            "lifecycle": s.lifecycle.value,
        }
    )


# --- Prompts (2) ---
# Prompts return fallback text (not errors) when no soul is loaded.


@mcp.prompt
def soul_system_prompt_template() -> str:
    """Complete system prompt for LLM context injection."""
    soul = _registry.active_soul
    if soul is None:
        return "No soul loaded. Call soul_birth first."
    return soul.to_system_prompt()


@mcp.prompt
def soul_introduction() -> str:
    """First-person self-introduction from the soul."""
    soul = _registry.active_soul
    if soul is None:
        return "No soul loaded. Call soul_birth first."
    core_values = soul.identity.core_values
    values = ", ".join(core_values) if core_values else "not yet defined"
    archetype = f", {soul.identity.archetype}" if soul.identity.archetype else ""
    return (
        f"I'm {soul.name}{archetype}."
        f" My core values are {values}."
        f" I'm currently feeling {soul.state.mood.value}"
        f" with {soul.state.energy:.0f}% energy."
    )


# --- Server lifecycle ---


def create_server() -> FastMCP:
    """Create and return the FastMCP server instance."""
    return mcp


def run_server() -> None:
    """Entry point for the soul-mcp console script."""
    mcp.run()
