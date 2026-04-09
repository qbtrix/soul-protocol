# runtime/context/lcm.py — LCMContext: reference ContextEngine implementation.
# Created: v0.3.0 — Lossless Context Management. Ingests messages into an immutable
# SQLite store, assembles context windows with automatic three-level compaction,
# and provides grep/expand/describe retrieval tools. Works standalone (no Soul needed).

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from soul_protocol.runtime.context.compaction import ThreeLevelCompactor, _estimate_tokens
from soul_protocol.runtime.context.retrieval import describe, expand, grep
from soul_protocol.runtime.context.store import SQLiteContextStore
from soul_protocol.spec.context.models import (
    AssembleResult,
    CompactionLevel,
    ContextMessage,
    ContextNode,
    DescribeResult,
    ExpandResult,
    GrepResult,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine


class LCMContext:
    """Lossless Context Management — reference ContextEngine implementation.

    Handles intra-session context: ingests conversation messages into an
    immutable SQLite store, assembles context windows that fit within token
    budgets using three-level escalation compaction, and provides retrieval
    tools to recover any information from the conversation history.

    Works standalone — does NOT require a Soul. Complementary to Soul Protocol's
    cross-session memory: Soul remembers who you are, LCM remembers what was said.

    Usage:
        lcm = LCMContext(db_path=":memory:")
        await lcm.initialize()

        msg_id = await lcm.ingest("user", "Hello, how are you?")
        result = await lcm.assemble(max_tokens=4000)

        # Search past messages
        hits = await lcm.grep("hello")

        # Recover originals from a compacted node
        expanded = await lcm.expand(node_id)

        # Get store metadata
        info = await lcm.describe()
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        engine: CognitiveEngine | None = None,
        *,
        default_max_tokens: int = 100_000,
        compaction_threshold: float = 0.85,
        summary_batch_size: int = 10,
    ) -> None:
        self._store = SQLiteContextStore(db_path)
        self._engine = engine
        self._default_max_tokens = default_max_tokens
        self._compaction_threshold = compaction_threshold
        self._compactor = ThreeLevelCompactor(
            self._store,
            engine,
            summary_batch_size=summary_batch_size,
        )
        self._initialized = False

    @property
    def store(self) -> SQLiteContextStore:
        """Access the underlying store (for advanced use / testing)."""
        return self._store

    async def initialize(self) -> None:
        """Initialize the SQLite store. Must be called before any operations."""
        await self._store.initialize()
        self._initialized = True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("LCMContext not initialized. Call initialize() first.")

    async def ingest(self, role: str, content: str, **metadata: object) -> str:
        """Ingest a new message into the context store.

        Estimates token count, appends to the immutable store, and triggers
        compaction if the total exceeds the threshold.

        Args:
            role: Message role (e.g., "user", "assistant", "system").
            content: Message content text.
            **metadata: Optional metadata key-value pairs.

        Returns:
            The message ID.
        """
        self._ensure_initialized()

        token_count = _estimate_tokens(content)
        message = ContextMessage(
            id=uuid.uuid4().hex[:12],
            role=role,
            content=content,
            token_count=token_count,
        )

        await self._store.append_message(message)

        # Check if compaction threshold is exceeded
        total_tokens = await self._store.total_message_tokens()
        threshold = int(self._default_max_tokens * self._compaction_threshold)
        if total_tokens > threshold:
            await self._compactor.compact(self._default_max_tokens)

        return message.id

    async def assemble(
        self, max_tokens: int | None = None, *, system_reserve: int = 0
    ) -> AssembleResult:
        """Assemble a context window that fits within max_tokens.

        Collects compacted nodes for covered ranges and verbatim messages
        for uncovered ranges, ordered by sequence. Applies compaction if
        the total exceeds the budget.

        Args:
            max_tokens: Token budget for the assembled context. Defaults to
                default_max_tokens from constructor.
            system_reserve: Tokens to reserve for system prompts, tool schemas,
                etc. Subtracted from max_tokens before assembly.

        Returns:
            AssembleResult with ordered nodes and token metadata.
        """
        self._ensure_initialized()

        effective_max = max_tokens if max_tokens is not None else self._default_max_tokens
        budget = effective_max - system_reserve
        if budget <= 0:
            return AssembleResult()

        # Compact if needed
        compaction_applied = False
        current_tokens = await self._compactor._current_context_tokens()
        if current_tokens > budget:
            saved = await self._compactor.compact(budget)
            compaction_applied = saved > 0

        # Build the assembled context
        nodes: list[ContextNode] = []
        total_tokens = 0

        # Get all nodes and messages (range coverage is derived from nodes below)
        all_nodes = await self._store.get_all_nodes()
        messages = await self._store.get_messages()

        # Build a map of the "best" node for each covered range
        # (highest compaction level = most compact)
        _level_order = {
            CompactionLevel.TRUNCATED: 3,
            CompactionLevel.BULLETS: 2,
            CompactionLevel.SUMMARY: 1,
            CompactionLevel.VERBATIM: 0,
        }

        # For each seq range, keep the most compact node
        range_nodes: dict[tuple[int, int], ContextNode] = {}
        for node in all_nodes:
            if node.level == CompactionLevel.VERBATIM:
                continue
            key = (node.seq_start, node.seq_end)
            existing = range_nodes.get(key)
            if existing is None or _level_order.get(node.level, 0) > _level_order.get(
                existing.level, 0
            ):
                range_nodes[key] = node

        # Build timeline: for each message, either use a compacted node or verbatim
        used_ranges: set[tuple[int, int]] = set()
        items: list[tuple[int, ContextNode]] = []  # (sort_key, node)

        for msg in messages:
            # Check if this message is covered by a compacted node
            covering_range = None
            for rng, node in range_nodes.items():
                if rng[0] <= msg.seq <= rng[1]:
                    covering_range = rng
                    break

            if covering_range and covering_range not in used_ranges:
                # Use the compacted node
                node = range_nodes[covering_range]
                items.append((covering_range[0], node))
                used_ranges.add(covering_range)
            elif covering_range:
                # Already added this range's node
                continue
            else:
                # Uncovered message — wrap in a verbatim node
                verbatim_node = ContextNode(
                    id=msg.id,
                    level=CompactionLevel.VERBATIM,
                    content=f"[{msg.role}] {msg.content}",
                    token_count=msg.token_count,
                    seq_start=msg.seq,
                    seq_end=msg.seq,
                )
                items.append((msg.seq, verbatim_node))

        # Sort by sequence and trim to budget
        items.sort(key=lambda x: x[0])
        for _, node in items:
            if total_tokens + node.token_count > budget:
                # Skip nodes that don't fit (prefer recent = keep later ones)
                continue
            nodes.append(node)
            total_tokens += node.token_count

        return AssembleResult(
            nodes=nodes,
            total_tokens=total_tokens,
            compaction_applied=compaction_applied,
        )

    async def grep(self, pattern: str, *, limit: int = 20) -> list[GrepResult]:
        """Search the immutable message store by regex pattern.

        Args:
            pattern: Regex pattern to match against message content.
            limit: Maximum number of results.

        Returns:
            List of GrepResult with message IDs, snippets, and metadata.
        """
        self._ensure_initialized()
        return await grep(self._store, pattern, limit=limit)

    async def expand(self, node_id: str) -> ExpandResult:
        """Expand a compacted node back to its original messages.

        Args:
            node_id: ID of the node to expand.

        Returns:
            ExpandResult with the node's level and original messages.
        """
        self._ensure_initialized()
        return await expand(self._store, node_id)

    async def describe(self) -> DescribeResult:
        """Return a metadata snapshot of the context store.

        Returns:
            DescribeResult with counts, tokens, date ranges, compaction stats.
        """
        self._ensure_initialized()
        return await describe(self._store)

    async def compact(self) -> int:
        """Force a compaction pass. Returns the number of tokens saved."""
        self._ensure_initialized()
        return await self._compactor.compact(self._default_max_tokens)

    async def close(self) -> None:
        """Close the underlying store."""
        await self._store.close()
        self._initialized = False
