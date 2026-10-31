# decide/candidates.py — Pick which existing memories a model decider should compare.
# Created: feat/soul-instinct — Model deciders judge contradictions pair by pair,
#   so the candidate set must be bounded. Unlike ContradictionDetector._find_similar
#   there is no minimum-overlap cutoff: "User loves steak" vs "User is vegetarian
#   now" share almost no tokens yet contradict, and catching exactly those cases
#   is the point of a model decider. Candidates are ranked by token overlap, then
#   recency, and superseded memories are skipped.

from __future__ import annotations

from soul_protocol.runtime.memory.dedup import jaccard_similarity
from soul_protocol.runtime.types import MemoryEntry

DEFAULT_MAX_CANDIDATES: int = 20


def select_candidates(
    new_content: str,
    existing: list[MemoryEntry],
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[MemoryEntry]:
    """Return up to ``max_candidates`` live memories, most related first."""
    live = [
        e
        for e in existing
        if not e.superseded and e.superseded_by is None and e.content.strip() != new_content.strip()
    ]
    live.sort(
        key=lambda e: (jaccard_similarity(new_content, e.content), e.created_at),
        reverse=True,
    )
    return live[:max_candidates]
