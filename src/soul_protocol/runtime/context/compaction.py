# runtime/context/compaction.py — Three-level escalation compactor for LCM.
# Created: v0.3.0 — Zero-cost path, Level 1 SUMMARY (LLM), Level 2 BULLETS (LLM),
# Level 3 TRUNCATED (deterministic). Uses CognitiveEngine for LLM calls when
# available; falls back to Level 3 without one. Guaranteed convergence.

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from soul_protocol.runtime.context.prompts import BULLETS_PROMPT, SUMMARY_PROMPT
from soul_protocol.spec.context.models import CompactionLevel, ContextNode

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.context.store import SQLiteContextStore

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


class ThreeLevelCompactor:
    """Three-level escalation compactor.

    Compaction levels (from least to most aggressive):
    1. SUMMARY — LLM summarizes a batch of verbatim messages into prose
    2. BULLETS — LLM re-compacts existing summaries into bullet points
    3. TRUNCATED — deterministic head-truncation (no LLM needed, always converges)

    The compactor only applies the minimum level needed to fit within budget.
    If no CognitiveEngine is provided, it skips straight to Level 3.
    """

    def __init__(
        self,
        store: SQLiteContextStore,
        engine: CognitiveEngine | None = None,
        *,
        summary_batch_size: int = 10,
    ) -> None:
        self._store = store
        self._engine = engine
        self._summary_batch_size = summary_batch_size

    async def compact(self, token_budget: int) -> int:
        """Run compaction until context fits within token_budget.

        Returns the number of tokens saved. Escalates through levels as needed.
        """
        initial_tokens = await self._current_context_tokens()
        if initial_tokens <= token_budget:
            return 0  # Zero-cost path: nothing to compact

        tokens_saved = 0

        # Level 1: Summarize oldest verbatim messages
        if self._engine:
            saved = await self._compact_level1(token_budget)
            tokens_saved += saved
            if await self._current_context_tokens() <= token_budget:
                return tokens_saved

        # Level 2: Compress existing summaries to bullets
        if self._engine:
            saved = await self._compact_level2(token_budget)
            tokens_saved += saved
            if await self._current_context_tokens() <= token_budget:
                return tokens_saved

        # Level 3: Deterministic truncation (guaranteed convergence)
        saved = await self._compact_level3(token_budget)
        tokens_saved += saved

        return tokens_saved

    async def _current_context_tokens(self) -> int:
        """Calculate current assembled context token count.

        Uses node token counts for compacted ranges, message token counts
        for uncovered messages.
        """
        total = 0

        # Get all non-verbatim nodes
        covered_ranges = await self._store.get_covered_seq_ranges()
        nodes = await self._store.get_all_nodes()

        # Add tokens from compacted nodes
        for node in nodes:
            if node.level != CompactionLevel.VERBATIM:
                total += node.token_count

        # Add tokens from uncovered messages
        messages = await self._store.get_messages()
        for msg in messages:
            if not self._is_seq_covered(msg.seq, covered_ranges):
                total += msg.token_count

        return total

    async def _compact_level1(self, token_budget: int) -> int:
        """Level 1 SUMMARY: Summarize batches of oldest verbatim messages."""
        assert self._engine is not None
        tokens_saved = 0
        covered_ranges = await self._store.get_covered_seq_ranges()

        # Get uncovered messages, oldest first
        messages = await self._store.get_messages()
        uncovered = [m for m in messages if not self._is_seq_covered(m.seq, covered_ranges)]

        if len(uncovered) <= self._summary_batch_size:
            return 0  # Not enough messages to form a batch worth summarizing

        # Take the oldest batch (leave recent messages verbatim)
        batch = uncovered[: self._summary_batch_size]
        batch_text = "\n".join(f"[{m.role}] {m.content}" for m in batch)
        batch_tokens = sum(m.token_count for m in batch)

        prompt = SUMMARY_PROMPT.format(messages=batch_text)
        try:
            summary = await self._engine.think(prompt)
            summary_tokens = _estimate_tokens(summary)

            node = ContextNode(
                id=uuid.uuid4().hex[:12],
                level=CompactionLevel.SUMMARY,
                content=summary,
                token_count=summary_tokens,
                children_ids=[m.id for m in batch],
                seq_start=batch[0].seq,
                seq_end=batch[-1].seq,
            )
            await self._store.insert_node(node)

            saved = batch_tokens - summary_tokens
            tokens_saved += max(0, saved)
            logger.debug(
                "L1 SUMMARY: compacted %d messages (%d→%d tokens)",
                len(batch),
                batch_tokens,
                summary_tokens,
            )
        except Exception:
            logger.warning("L1 SUMMARY failed, will escalate to next level")

        return tokens_saved

    async def _compact_level2(self, token_budget: int) -> int:
        """Level 2 BULLETS: Re-compact existing summaries into bullet points."""
        assert self._engine is not None
        tokens_saved = 0

        summary_nodes = await self._store.get_nodes_by_level(CompactionLevel.SUMMARY)
        if not summary_nodes:
            return 0

        for node in summary_nodes:
            if await self._current_context_tokens() <= token_budget:
                break

            prompt = BULLETS_PROMPT.format(text=node.content)
            try:
                bullets = await self._engine.think(prompt)
                bullet_tokens = _estimate_tokens(bullets)

                new_node = ContextNode(
                    id=uuid.uuid4().hex[:12],
                    level=CompactionLevel.BULLETS,
                    content=bullets,
                    token_count=bullet_tokens,
                    children_ids=[node.id],
                    seq_start=node.seq_start,
                    seq_end=node.seq_end,
                )
                await self._store.insert_node(new_node)

                saved = node.token_count - bullet_tokens
                tokens_saved += max(0, saved)
                logger.debug(
                    "L2 BULLETS: compacted node %s (%d→%d tokens)",
                    node.id,
                    node.token_count,
                    bullet_tokens,
                )
            except Exception:
                logger.warning("L2 BULLETS failed for node %s, will escalate", node.id)

        return tokens_saved

    async def _compact_level3(self, token_budget: int) -> int:
        """Level 3 TRUNCATED: Deterministic head-truncation. Always converges."""
        tokens_saved = 0
        current = await self._current_context_tokens()

        if current <= token_budget:
            return 0

        # Add a margin for the truncated node's own tokens (~20 tokens)
        truncation_overhead = 20
        overflow = current - token_budget + truncation_overhead

        # Get uncovered messages, oldest first
        covered_ranges = await self._store.get_covered_seq_ranges()
        messages = await self._store.get_messages()
        uncovered = [m for m in messages if not self._is_seq_covered(m.seq, covered_ranges)]

        # Also consider existing summary/bullet nodes (oldest first)
        nodes = await self._store.get_all_nodes()
        compacted_nodes = [n for n in nodes if n.level != CompactionLevel.VERBATIM]
        compacted_nodes.sort(key=lambda n: n.seq_start)

        # Truncate oldest uncovered messages first
        truncated_items: list[tuple[str, int, int, int]] = []  # (id, seq_start, seq_end, tokens)

        for msg in uncovered:
            if overflow <= 0:
                break
            truncated_items.append((msg.id, msg.seq, msg.seq, msg.token_count))
            overflow -= msg.token_count
            tokens_saved += msg.token_count

        # If still overflowing, truncate oldest compacted nodes
        for node in compacted_nodes:
            if overflow <= 0:
                break
            truncated_items.append((node.id, node.seq_start, node.seq_end, node.token_count))
            overflow -= node.token_count
            tokens_saved += node.token_count

        if truncated_items:
            seq_start = min(t[1] for t in truncated_items)
            seq_end = max(t[2] for t in truncated_items)
            child_ids = [t[0] for t in truncated_items]

            # Create a truncated node with minimal content
            truncated_content = (
                f"[{len(truncated_items)} items truncated, seq {seq_start}-{seq_end}]"
            )
            truncated_tokens = _estimate_tokens(truncated_content)

            node = ContextNode(
                id=uuid.uuid4().hex[:12],
                level=CompactionLevel.TRUNCATED,
                content=truncated_content,
                children_ids=child_ids,
                token_count=truncated_tokens,
                seq_start=seq_start,
                seq_end=seq_end,
            )
            await self._store.insert_node(node)

            # Account for the truncated node's own tokens
            tokens_saved -= truncated_tokens
            logger.debug(
                "L3 TRUNCATED: %d items, saved %d tokens",
                len(truncated_items),
                tokens_saved,
            )

        return max(0, tokens_saved)

    @staticmethod
    def _is_seq_covered(seq: int, ranges: list[tuple[int, int]]) -> bool:
        """Check if a sequence number falls within any covered range."""
        return any(start <= seq <= end for start, end in ranges)
