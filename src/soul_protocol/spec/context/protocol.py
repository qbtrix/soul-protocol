# spec/context/protocol.py — ContextEngine protocol for Lossless Context Management.
# Created: v0.3.0 — The protocol interface that any context engine must implement.
# Consumers provide an implementation; the runtime ships a reference one (LCMContext).

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AssembleResult, DescribeResult, ExpandResult, GrepResult


@runtime_checkable
class ContextEngine(Protocol):
    """Interface for lossless context management.

    The context engine ingests messages, assembles context windows with
    automatic compaction, and provides retrieval tools (grep, expand, describe)
    to recover any information from the conversation history.

    Simplest implementation:
        class MyContext:
            async def ingest(self, role, content, **metadata) -> str:
                ...  # store message, return ID
            async def assemble(self, max_tokens, *, system_reserve=0) -> AssembleResult:
                ...  # build context window
            async def grep(self, pattern, *, limit=20) -> list[GrepResult]:
                ...  # search messages
            async def expand(self, node_id) -> ExpandResult:
                ...  # recover originals from compacted node
            async def describe(self) -> DescribeResult:
                ...  # metadata snapshot
            async def compact(self) -> int:
                ...  # force compaction, return tokens saved
    """

    async def ingest(self, role: str, content: str, **metadata: object) -> str:
        """Ingest a new message into the context store.

        Returns the message ID. The message is immutable once stored.
        """
        ...

    async def assemble(self, max_tokens: int, *, system_reserve: int = 0) -> AssembleResult:
        """Assemble a context window that fits within max_tokens.

        Applies compaction as needed. system_reserve tokens are subtracted
        from the budget before assembly (for system prompts, tool schemas, etc).
        """
        ...

    async def grep(self, pattern: str, *, limit: int = 20) -> list[GrepResult]:
        """Search the immutable message store by regex pattern.

        Returns matching messages with content snippets, ordered by recency.
        """
        ...

    async def expand(self, node_id: str) -> ExpandResult:
        """Expand a compacted node back to its original messages.

        Walks the DAG edges to recover the verbatim content that was
        summarized or truncated.
        """
        ...

    async def describe(self) -> DescribeResult:
        """Return a metadata snapshot of the context store.

        Includes counts, token totals, date ranges, and compaction statistics.
        """
        ...

    async def compact(self) -> int:
        """Force a compaction pass. Returns the number of tokens saved.

        Useful for proactive compaction before a large ingest, or for
        testing compaction behavior.
        """
        ...
