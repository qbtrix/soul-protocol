# memory/compression.py — MemoryCompressor for rule-based memory compression.
# Created: 2026-03-06 — SimpleMem-inspired compression pipeline. No LLM needed.
#   Supports summarization, deduplication via token overlap, importance-based
#   pruning, and export splitting for .soul files.

from __future__ import annotations

from datetime import datetime, timedelta

from soul_protocol.types import MemoryEntry


def _token_overlap(a: str, b: str) -> float:
    """Jaccard token-overlap score between two strings (0.0 to 1.0)."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


class MemoryCompressor:
    """SimpleMem-inspired memory compression.

    All methods are rule-based — no LLM calls required. Designed to reduce
    memory footprint while preserving the most important information.
    """

    def summarize_memories(self, memories: list[MemoryEntry], max_tokens: int = 500) -> str:
        """Compress multiple memories into a summary string.

        Rule-based compression strategy:
          1. Sort by importance (descending)
          2. Deduplicate similar content (token overlap > 0.7)
          3. Group by memory type
          4. Concatenate up to max_tokens worth of content

        Args:
            memories: List of MemoryEntry objects to summarize.
            max_tokens: Approximate maximum word count for the summary.

        Returns:
            A compressed summary string.
        """
        if not memories:
            return ""

        # Sort by importance descending, then recency
        sorted_mems = sorted(
            memories,
            key=lambda m: (-m.importance, -m.created_at.timestamp()),
        )

        # Deduplicate
        unique: list[MemoryEntry] = []
        for mem in sorted_mems:
            is_dup = any(
                _token_overlap(mem.content, u.content) > 0.7 for u in unique
            )
            if not is_dup:
                unique.append(mem)

        # Group by type
        groups: dict[str, list[str]] = {}
        for mem in unique:
            type_label = mem.type.value if hasattr(mem.type, "value") else str(mem.type)
            groups.setdefault(type_label, []).append(mem.content)

        # Build summary respecting token budget
        lines: list[str] = []
        token_count = 0

        for type_label, contents in groups.items():
            header = f"[{type_label}]"
            header_tokens = len(header.split())

            if token_count + header_tokens > max_tokens:
                break

            lines.append(header)
            token_count += header_tokens

            for content in contents:
                content_tokens = len(content.split())
                if token_count + content_tokens > max_tokens:
                    break
                lines.append(f"- {content}")
                token_count += content_tokens

        return "\n".join(lines)

    def deduplicate(
        self, memories: list[MemoryEntry], similarity_threshold: float = 0.8
    ) -> list[MemoryEntry]:
        """Remove near-duplicate memories using token overlap.

        When two memories exceed the similarity threshold, the one with
        higher importance is kept. If importance is equal, the more recent
        one is kept.

        Args:
            memories: List of memories to deduplicate.
            similarity_threshold: Jaccard overlap threshold (0.0 to 1.0).

        Returns:
            Deduplicated list of memories.
        """
        if not memories:
            return []

        # Sort by importance desc, then recency desc — first seen wins
        sorted_mems = sorted(
            memories,
            key=lambda m: (-m.importance, -m.created_at.timestamp()),
        )

        unique: list[MemoryEntry] = []
        for mem in sorted_mems:
            is_dup = any(
                _token_overlap(mem.content, u.content) >= similarity_threshold
                for u in unique
            )
            if not is_dup:
                unique.append(mem)

        return unique

    def prune_by_importance(
        self,
        memories: list[MemoryEntry],
        min_importance: int = 3,
        max_age_days: int = 365,
    ) -> tuple[list[MemoryEntry], list[MemoryEntry]]:
        """Split memories into keep/prune based on importance and age.

        A memory is pruned if:
          - Its importance is below min_importance, OR
          - It is older than max_age_days AND its importance is below 7
            (high-importance memories are always kept regardless of age)

        Args:
            memories: List of memories to evaluate.
            min_importance: Minimum importance to keep (1-10).
            max_age_days: Maximum age in days before considering for pruning.

        Returns:
            Tuple of (keep, pruned) memory lists.
        """
        now = datetime.now()
        cutoff = now - timedelta(days=max_age_days)

        keep: list[MemoryEntry] = []
        pruned: list[MemoryEntry] = []

        for mem in memories:
            if mem.importance < min_importance:
                pruned.append(mem)
            elif mem.created_at < cutoff and mem.importance < 7:
                pruned.append(mem)
            else:
                keep.append(mem)

        return keep, pruned

    def compress_for_export(
        self, memories: list[MemoryEntry], max_inline: int = 500
    ) -> tuple[list[MemoryEntry], list[MemoryEntry]]:
        """Split memories for .soul file: inline (top N by importance) vs external.

        The top `max_inline` memories by importance are included inline in the
        .soul archive. The rest are marked as external (stored separately).

        Args:
            memories: All memories to split.
            max_inline: Maximum number of memories to include inline.

        Returns:
            Tuple of (inline, external) memory lists.
        """
        sorted_mems = sorted(
            memories,
            key=lambda m: (-m.importance, -m.created_at.timestamp()),
        )

        inline = sorted_mems[:max_inline]
        external = sorted_mems[max_inline:]

        return inline, external
