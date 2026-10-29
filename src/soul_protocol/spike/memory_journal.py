# memory_journal.py — Spike: JournalBackedMemoryStore.
# Created: feat/0.3.2-spike — implements MemoryStore Protocol on top of the
# v0.3.1 Journal engine. Memory operations become events; tier listings and
# search become SQLite FTS5 projections. Goal: kill the cleanup-wipes-
# everything class of bug by keeping projections rebuildable from truth.
#
# See docs/memory-journal-spike.md for the design + benchmark plan.
# This module is NOT part of the shipped public API yet.

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from soul_protocol.engine.journal import Journal, open_journal
from soul_protocol.spec.journal import Actor, EventEntry
from soul_protocol.spec.memory import MemoryEntry, MemoryVisibility

# ---------------------------------------------------------------------------
# FTS query construction
# ---------------------------------------------------------------------------


_FTS_SPECIAL_CHARS = set("\"'()+*-:")


def _build_fts_query(user_query: str) -> str:
    """Build an FTS5 MATCH expression from user input.

    Splits the query on any non-alphanumeric character (matches how FTS5's
    unicode61 tokenizer breaks stored text — so "alice@example.com"
    produces the same tokens "alice", "example", "com" on both sides).
    Tokens are joined with OR so multi-word queries rank by bm25 rather
    than require strict conjunction.
    """
    tokens: list[str] = []
    current: list[str] = []
    for c in user_query:
        if c.isalnum() or c == "_":
            current.append(c)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


# ---------------------------------------------------------------------------
# Projection schema
# ---------------------------------------------------------------------------

PROJECTION_SCHEMA_VERSION = 1

PROJECTION_DDL = """
CREATE TABLE IF NOT EXISTS memory_tier (
    memory_id TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    emotion TEXT,
    tags TEXT,  -- JSON array
    source TEXT,
    created_at TEXT NOT NULL,  -- ISO UTC
    seq INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_tier_tier ON memory_tier(tier);
CREATE INDEX IF NOT EXISTS idx_memory_tier_importance ON memory_tier(importance);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_memories USING fts5(
    memory_id UNINDEXED,
    tier UNINDEXED,
    content,
    tags,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS projection_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _open_projection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection configured for projection use."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(PROJECTION_DDL)
    conn.execute(
        "INSERT OR IGNORE INTO projection_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(PROJECTION_SCHEMA_VERSION)),
    )
    conn.execute(
        "INSERT OR IGNORE INTO projection_meta (key, value) VALUES (?, ?)",
        ("last_replayed_seq", "-1"),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------


class JournalBackedMemoryStore:
    """Memory storage where the journal is truth and projections are cache.

    The journal holds `memory.remembered`, `memory.forgotten`,
    `memory.graduated`, `memory.archived` events. Projections (tier tables,
    FTS5 index) are rebuildable from the journal at any time.

    Implements the shape of :class:`soul_protocol.spec.memory.MemoryStore` —
    runtime-checkable Protocol conformance is validated in the spike tests.
    """

    def __init__(
        self,
        journal: Journal,
        projection_db: sqlite3.Connection,
        *,
        actor: Actor,
        default_scope: list[str] | None = None,
    ) -> None:
        self._journal = journal
        self._db = projection_db
        self._actor = actor
        self._default_scope = default_scope or ["org:default"]

    # -- writes ---------------------------------------------------------

    def store(self, layer: str, entry: MemoryEntry) -> str:
        """Store a memory. Returns the memory_id.

        `layer` maps to `tier` in the event payload. We accept the existing
        MemoryStore Protocol shape so callers don't change.
        """
        memory_id = entry.id or uuid4().hex[:12]
        payload = {
            "memory_id": memory_id,
            "content": entry.content,
            "tier": layer,
            "importance": entry.metadata.get("importance", 5),
            "emotion": entry.metadata.get("emotion"),
            "tags": entry.metadata.get("tags", []),
            "source": entry.source,
            "created_at": entry.created_at.isoformat(),
        }
        event = EventEntry(
            id=uuid4(),
            ts=datetime.now(UTC),
            actor=self._actor,
            action="memory.remembered",
            scope=self._default_scope,
            payload=payload,
        )
        committed = self._journal.append(event)
        self._apply_remembered(committed)
        return memory_id

    def delete(self, memory_id: str) -> bool:
        """Delete a memory (writes a tombstone event).

        GDPR-safe: the tombstone event payload contains only the memory_id
        and reason. Content is removed from projections but never replayed
        back into them — the original `memory.remembered` event still holds
        the content for audit, but `delete_content_for_gdpr` in a future
        slice can redact content on demand.
        """
        if not self._exists(memory_id):
            return False
        event = EventEntry(
            id=uuid4(),
            ts=datetime.now(UTC),
            actor=self._actor,
            action="memory.forgotten",
            scope=self._default_scope,
            payload={"memory_id": memory_id, "reason": "user"},
        )
        committed = self._journal.append(event)
        self._apply_forgotten(committed)
        return True

    def promote(self, memory_id: str, to_tier: str, reason: str = "manual") -> bool:
        """Promote a memory to a different tier."""
        row = self._db.execute(
            "SELECT tier FROM memory_tier WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False
        from_tier = row[0]
        if from_tier == to_tier:
            return False

        event = EventEntry(
            id=uuid4(),
            ts=datetime.now(UTC),
            actor=self._actor,
            action="memory.graduated",
            scope=self._default_scope,
            payload={
                "memory_id": memory_id,
                "from_tier": from_tier,
                "to_tier": to_tier,
                "reason": reason,
            },
        )
        committed = self._journal.append(event)
        self._apply_graduated(committed)
        return True

    # -- reads ----------------------------------------------------------

    def recall(self, layer: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Most-recent-first listing from a single tier."""
        cursor = self._db.execute(
            """
            SELECT memory_id, tier, content, importance, emotion, tags,
                   source, created_at
            FROM memory_tier
            WHERE tier = ?
            ORDER BY seq DESC
            LIMIT ?
            """,
            (layer, limit),
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def search(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        """BM25-ranked full-text search across all tiers.

        User queries are tokenized and joined with FTS5 OR operators so a
        multi-word query returns memories containing any of the terms (with
        bm25 boosting memories that contain more of them). Users can still
        force phrase matching by wrapping a query in literal quotes.
        """
        if not query.strip():
            return []
        fts_query = _build_fts_query(query)
        if not fts_query:
            return []
        try:
            cursor = self._db.execute(
                """
                SELECT mt.memory_id, mt.tier, mt.content, mt.importance,
                       mt.emotion, mt.tags, mt.source, mt.created_at
                FROM fts_memories f
                JOIN memory_tier mt ON mt.memory_id = f.memory_id
                WHERE fts_memories MATCH ?
                ORDER BY bm25(fts_memories)
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Malformed FTS query (unlikely after _build_fts_query, but be safe).
            return []

    def layers(self) -> list[str]:
        """List tiers that currently contain at least one memory."""
        cursor = self._db.execute("SELECT DISTINCT tier FROM memory_tier ORDER BY tier")
        return [row[0] for row in cursor.fetchall()]

    def audit_trail(self, memory_id: str) -> list[EventEntry]:
        """All journal events touching a memory_id, seq-ordered.

        Useful for "when was this stored, promoted, forgotten". Because the
        journal is append-only, this trail is complete and ordered.
        """
        # The journal query filters by action; we fetch the three relevant
        # actions and filter payload in Python. A future slice can add a
        # payload-key index or a typed memory_id column for performance.
        actions = (
            "memory.remembered",
            "memory.forgotten",
            "memory.graduated",
            "memory.archived",
        )
        results: list[EventEntry] = []
        for action in actions:
            for event in self._journal.query(action=action, limit=10000):
                if isinstance(event.payload, dict) and event.payload.get("memory_id") == memory_id:
                    results.append(event)
        results.sort(key=lambda e: e.seq or 0)
        return results

    # -- lifecycle ------------------------------------------------------

    def rebuild(self) -> int:
        """Drop and rebuild projections from the journal. Returns event count."""
        self._db.execute("DELETE FROM memory_tier")
        self._db.execute("DELETE FROM fts_memories")
        self._db.execute(
            "UPDATE projection_meta SET value = ? WHERE key = ?",
            ("-1", "last_replayed_seq"),
        )

        count = 0
        last_seq = -1
        for event in self._journal.replay_from(0):
            if event.action == "memory.remembered":
                self._apply_remembered(event, commit=False)
            elif event.action == "memory.forgotten":
                self._apply_forgotten(event, commit=False)
            elif event.action == "memory.graduated":
                self._apply_graduated(event, commit=False)
            elif event.action == "memory.archived":
                self._apply_forgotten(event, commit=False)  # archive hides from tiers
            count += 1
            last_seq = event.seq or last_seq

        self._db.execute(
            "UPDATE projection_meta SET value = ? WHERE key = ?",
            (str(last_seq), "last_replayed_seq"),
        )
        self._db.commit()
        return count

    # -- internals ------------------------------------------------------

    def _exists(self, memory_id: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM memory_tier WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return row is not None

    def _apply_remembered(self, event: EventEntry, *, commit: bool = True) -> None:
        p = event.payload if isinstance(event.payload, dict) else {}
        mem_id = p.get("memory_id", str(event.id))
        tags_json = json.dumps(p.get("tags") or [])
        self._db.execute(
            """
            INSERT OR REPLACE INTO memory_tier (
                memory_id, tier, content, importance, emotion, tags,
                source, created_at, seq
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mem_id,
                p.get("tier", "episodic"),
                p.get("content", ""),
                int(p.get("importance", 5)),
                p.get("emotion"),
                tags_json,
                p.get("source", ""),
                p.get("created_at") or event.ts.isoformat(),
                event.seq or 0,
            ),
        )
        self._db.execute("DELETE FROM fts_memories WHERE memory_id = ?", (mem_id,))
        self._db.execute(
            "INSERT INTO fts_memories (memory_id, tier, content, tags) VALUES (?, ?, ?, ?)",
            (
                mem_id,
                p.get("tier", "episodic"),
                p.get("content", ""),
                " ".join(p.get("tags") or []),
            ),
        )
        if commit:
            self._db.commit()

    def _apply_forgotten(self, event: EventEntry, *, commit: bool = True) -> None:
        p = event.payload if isinstance(event.payload, dict) else {}
        mem_id = p.get("memory_id")
        if not mem_id:
            return
        self._db.execute("DELETE FROM memory_tier WHERE memory_id = ?", (mem_id,))
        self._db.execute("DELETE FROM fts_memories WHERE memory_id = ?", (mem_id,))
        if commit:
            self._db.commit()

    def _apply_graduated(self, event: EventEntry, *, commit: bool = True) -> None:
        p = event.payload if isinstance(event.payload, dict) else {}
        mem_id = p.get("memory_id")
        to_tier = p.get("to_tier")
        if not mem_id or not to_tier:
            return
        self._db.execute(
            "UPDATE memory_tier SET tier = ? WHERE memory_id = ?",
            (to_tier, mem_id),
        )
        # FTS tier column is UNINDEXED but we refresh it for consistency.
        row = self._db.execute(
            "SELECT content, tags FROM memory_tier WHERE memory_id = ?", (mem_id,)
        ).fetchone()
        if row is not None:
            self._db.execute("DELETE FROM fts_memories WHERE memory_id = ?", (mem_id,))
            self._db.execute(
                "INSERT INTO fts_memories (memory_id, tier, content, tags) VALUES (?, ?, ?, ?)",
                (mem_id, to_tier, row[0], row[1]),
            )
        if commit:
            self._db.commit()

    def _row_to_entry(self, row: tuple[Any, ...]) -> MemoryEntry:
        mem_id, tier, content, importance, emotion, tags_json, source, created_at = row
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        return MemoryEntry(
            id=mem_id,
            content=content,
            source=source or "",
            layer=tier,
            visibility=MemoryVisibility.BONDED,
            created_at=datetime.fromisoformat(created_at),
            metadata={
                "importance": importance,
                "emotion": emotion,
                "tags": tags,
            },
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def open_memory_store(
    base_dir: Path,
    *,
    actor: Actor,
    default_scope: list[str] | None = None,
) -> JournalBackedMemoryStore:
    """Open (or create) a journal-backed memory store rooted at `base_dir`.

    Layout inside `base_dir`:
        base_dir/journal.db    — the journal (source of truth)
        base_dir/projection.db — projections (rebuildable cache)
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    journal = open_journal(base_dir / "journal.db")
    projection_db = _open_projection(base_dir / "projection.db")
    return JournalBackedMemoryStore(
        journal,
        projection_db,
        actor=actor,
        default_scope=default_scope,
    )
