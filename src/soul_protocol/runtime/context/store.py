# runtime/context/store.py — SQLiteContextStore: immutable message store + DAG.
# Created: v0.3.0 — Three tables (messages, nodes, node_children). Append-only
# messages, DAG summary nodes with parent-child edges. Uses stdlib sqlite3 with
# asyncio.to_thread() for async wrapping. Zero external dependencies.

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from soul_protocol.spec.context.models import (
    CompactionLevel,
    ContextMessage,
    ContextNode,
    DescribeResult,
    GrepResult,
)


class SQLiteContextStore:
    """Immutable SQLite store for conversation messages and compaction DAG.

    Three tables:
    - messages: append-only conversation messages (NEVER updated or deleted)
    - nodes: DAG nodes representing compacted summaries
    - node_children: edges linking parent nodes to their child node/message IDs

    All writes go through asyncio.to_thread() so the store is safe to use
    from async code without blocking the event loop.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._seq_counter = 0

    async def initialize(self) -> None:
        """Create tables and load the current sequence counter."""
        self._conn = await asyncio.to_thread(self._connect)
        await asyncio.to_thread(self._create_tables)
        # Load current max seq so we can continue from where we left off
        row = await asyncio.to_thread(self._execute_fetchone, "SELECT MAX(seq) FROM messages")
        if row and row[0] is not None:
            self._seq_counter = row[0]

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False is required because every store method routes
        # the actual SQLite call through asyncio.to_thread(), which uses a shared
        # ThreadPoolExecutor — the connection is created on one worker thread but
        # subsequent reads/writes can land on any worker. Serialized access is
        # guaranteed by the async call sites (one to_thread at a time), so the
        # usual reason for keeping the check is not a concern here.
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                seq INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL DEFAULT 'verbatim',
                content TEXT NOT NULL DEFAULT '',
                token_count INTEGER NOT NULL DEFAULT 0,
                seq_start INTEGER NOT NULL DEFAULT 0,
                seq_end INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS node_children (
                parent_id TEXT NOT NULL,
                child_id TEXT NOT NULL,
                child_type TEXT NOT NULL DEFAULT 'message',
                PRIMARY KEY (parent_id, child_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_seq ON messages(seq);
            CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
            CREATE INDEX IF NOT EXISTS idx_nodes_level ON nodes(level);
            CREATE INDEX IF NOT EXISTS idx_nodes_seq_range ON nodes(seq_start, seq_end);
            """
        )

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._conn

    def _execute_fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        conn = self._ensure_conn()
        cursor = conn.execute(sql, params)
        return cursor.fetchone()

    def _execute_fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        conn = self._ensure_conn()
        cursor = conn.execute(sql, params)
        return cursor.fetchall()

    # -----------------------------------------------------------------------
    # Message operations (append-only)
    # -----------------------------------------------------------------------

    async def append_message(self, message: ContextMessage) -> ContextMessage:
        """Append a message to the store. Assigns seq number. Returns updated message."""
        self._seq_counter += 1
        message.seq = self._seq_counter

        def _insert() -> None:
            conn = self._ensure_conn()
            conn.execute(
                """INSERT INTO messages (id, role, content, token_count, seq, created_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.id,
                    message.role,
                    message.content,
                    message.token_count,
                    message.seq,
                    message.created_at.isoformat(),
                    "{}",
                ),
            )
            conn.commit()

        await asyncio.to_thread(_insert)
        return message

    async def get_messages(
        self,
        *,
        seq_start: int | None = None,
        seq_end: int | None = None,
        limit: int | None = None,
    ) -> list[ContextMessage]:
        """Retrieve messages, optionally filtered by sequence range."""
        sql = "SELECT id, role, content, token_count, seq, created_at, metadata FROM messages"
        conditions: list[str] = []
        params: list[int] = []

        if seq_start is not None:
            conditions.append("seq >= ?")
            params.append(seq_start)
        if seq_end is not None:
            conditions.append("seq <= ?")
            params.append(seq_end)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY seq ASC"

        if limit is not None:
            sql += f" LIMIT {limit}"

        rows = await asyncio.to_thread(self._execute_fetchall, sql, tuple(params))
        return [self._row_to_message(row) for row in rows]

    async def get_message_by_id(self, message_id: str) -> ContextMessage | None:
        """Get a single message by ID."""
        row = await asyncio.to_thread(
            self._execute_fetchone,
            "SELECT id, role, content, token_count, seq, created_at, metadata FROM messages WHERE id = ?",
            (message_id,),
        )
        return self._row_to_message(row) if row else None

    async def count_messages(self) -> int:
        """Count total messages in the store."""
        row = await asyncio.to_thread(self._execute_fetchone, "SELECT COUNT(*) FROM messages")
        return row[0] if row else 0

    async def total_message_tokens(self) -> int:
        """Sum of all message token counts."""
        row = await asyncio.to_thread(
            self._execute_fetchone, "SELECT COALESCE(SUM(token_count), 0) FROM messages"
        )
        return row[0] if row else 0

    async def get_date_range(self) -> tuple[datetime | None, datetime | None]:
        """Get the earliest and latest message timestamps."""
        row = await asyncio.to_thread(
            self._execute_fetchone,
            "SELECT MIN(created_at), MAX(created_at) FROM messages",
        )
        if not row or row[0] is None:
            return (None, None)
        return (
            datetime.fromisoformat(row[0]),
            datetime.fromisoformat(row[1]),
        )

    async def grep_messages(self, pattern: str, *, limit: int = 20) -> list[GrepResult]:
        """Search messages by regex pattern. Returns matches ordered by recency."""
        # Fetch all messages and filter in Python (sqlite3 has no regex by default)
        rows = await asyncio.to_thread(
            self._execute_fetchall,
            "SELECT id, role, content, seq, created_at FROM messages ORDER BY seq DESC",
        )

        compiled = re.compile(pattern, re.IGNORECASE)
        results: list[GrepResult] = []

        for row in rows:
            msg_id, role, content, seq, created_at_str = row
            match = compiled.search(content)
            if match:
                # Build a snippet around the match
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."

                results.append(
                    GrepResult(
                        message_id=msg_id,
                        seq=seq,
                        role=role,
                        content_snippet=snippet,
                        created_at=datetime.fromisoformat(created_at_str),
                    )
                )
                if len(results) >= limit:
                    break

        return results

    # -----------------------------------------------------------------------
    # Node operations (DAG)
    # -----------------------------------------------------------------------

    async def insert_node(self, node: ContextNode) -> ContextNode:
        """Insert a DAG node and its child edges."""

        def _insert() -> None:
            conn = self._ensure_conn()
            conn.execute(
                """INSERT INTO nodes (id, level, content, token_count, seq_start, seq_end, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    node.id,
                    node.level.value,
                    node.content,
                    node.token_count,
                    node.seq_start,
                    node.seq_end,
                    node.created_at.isoformat(),
                ),
            )
            for child_id in node.children_ids:
                conn.execute(
                    "INSERT INTO node_children (parent_id, child_id, child_type) VALUES (?, ?, ?)",
                    (node.id, child_id, "message"),
                )
            conn.commit()

        await asyncio.to_thread(_insert)
        return node

    async def get_node(self, node_id: str) -> ContextNode | None:
        """Get a single node by ID, including its child IDs."""
        row = await asyncio.to_thread(
            self._execute_fetchone,
            "SELECT id, level, content, token_count, seq_start, seq_end, created_at FROM nodes WHERE id = ?",
            (node_id,),
        )
        if not row:
            return None

        children_rows = await asyncio.to_thread(
            self._execute_fetchall,
            "SELECT child_id FROM node_children WHERE parent_id = ?",
            (node_id,),
        )
        children_ids = [r[0] for r in children_rows]

        return ContextNode(
            id=row[0],
            level=CompactionLevel(row[1]),
            content=row[2],
            token_count=row[3],
            seq_start=row[4],
            seq_end=row[5],
            children_ids=children_ids,
            created_at=datetime.fromisoformat(row[6]),
        )

    async def get_nodes_by_level(self, level: CompactionLevel) -> list[ContextNode]:
        """Get all nodes at a specific compaction level."""
        rows = await asyncio.to_thread(
            self._execute_fetchall,
            "SELECT id, level, content, token_count, seq_start, seq_end, created_at FROM nodes WHERE level = ? ORDER BY seq_start ASC",
            (level.value,),
        )

        nodes: list[ContextNode] = []
        for row in rows:
            children_rows = await asyncio.to_thread(
                self._execute_fetchall,
                "SELECT child_id FROM node_children WHERE parent_id = ?",
                (row[0],),
            )
            nodes.append(
                ContextNode(
                    id=row[0],
                    level=CompactionLevel(row[1]),
                    content=row[2],
                    token_count=row[3],
                    seq_start=row[4],
                    seq_end=row[5],
                    children_ids=[r[0] for r in children_rows],
                    created_at=datetime.fromisoformat(row[6]),
                )
            )
        return nodes

    async def get_all_nodes(self) -> list[ContextNode]:
        """Get all nodes ordered by seq_start."""
        rows = await asyncio.to_thread(
            self._execute_fetchall,
            "SELECT id, level, content, token_count, seq_start, seq_end, created_at FROM nodes ORDER BY seq_start ASC",
        )

        nodes: list[ContextNode] = []
        for row in rows:
            children_rows = await asyncio.to_thread(
                self._execute_fetchall,
                "SELECT child_id FROM node_children WHERE parent_id = ?",
                (row[0],),
            )
            nodes.append(
                ContextNode(
                    id=row[0],
                    level=CompactionLevel(row[1]),
                    content=row[2],
                    token_count=row[3],
                    seq_start=row[4],
                    seq_end=row[5],
                    children_ids=[r[0] for r in children_rows],
                    created_at=datetime.fromisoformat(row[6]),
                )
            )
        return nodes

    async def count_nodes(self) -> int:
        """Count total nodes."""
        row = await asyncio.to_thread(self._execute_fetchone, "SELECT COUNT(*) FROM nodes")
        return row[0] if row else 0

    async def compaction_stats(self) -> dict[str, int]:
        """Count nodes by compaction level."""
        rows = await asyncio.to_thread(
            self._execute_fetchall,
            "SELECT level, COUNT(*) FROM nodes GROUP BY level",
        )
        return {row[0]: row[1] for row in rows}

    async def get_covered_seq_ranges(self) -> list[tuple[int, int]]:
        """Get sequence ranges covered by non-verbatim nodes.

        Returns sorted list of (seq_start, seq_end) tuples for all nodes
        that are SUMMARY, BULLETS, or TRUNCATED level.
        """
        rows = await asyncio.to_thread(
            self._execute_fetchall,
            """SELECT seq_start, seq_end FROM nodes
               WHERE level != 'verbatim'
               ORDER BY seq_start ASC""",
        )
        return [(row[0], row[1]) for row in rows]

    # -----------------------------------------------------------------------
    # Describe
    # -----------------------------------------------------------------------

    async def describe(self) -> DescribeResult:
        """Build a metadata snapshot of the store."""
        total_messages = await self.count_messages()
        total_nodes = await self.count_nodes()
        total_tokens = await self.total_message_tokens()
        date_range = await self.get_date_range()
        stats = await self.compaction_stats()

        return DescribeResult(
            total_messages=total_messages,
            total_nodes=total_nodes,
            total_tokens=total_tokens,
            date_range=date_range,
            compaction_stats=stats,
        )

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _row_to_message(row: tuple) -> ContextMessage:
        return ContextMessage(
            id=row[0],
            role=row[1],
            content=row[2],
            token_count=row[3],
            seq=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
