# memory/dedup.py — Deduplication pipeline for semantic memory reconciliation.
# Created: Phase 2 memory-runtime-v2
#   - reconcile_fact() uses token overlap (Jaccard) to decide CREATE/SKIP/MERGE
#   - SKIP: >0.85 similarity (near-duplicate), MERGE: 0.6-0.85 (update existing),
#     CREATE: <0.6 (genuinely new fact)
#   - Uses tokenize() from search.py with min_length=2 for dedup so that short
#     but meaningful tokens (Go, JS, AI, ML, UI, etc.) are preserved.

from __future__ import annotations

from soul_protocol.runtime.memory.search import tokenize
from soul_protocol.runtime.types import MemoryEntry

# Common 2-letter English stopwords to filter when lowering the minimum token
# length to 2.  These are function words / pronouns that add noise to Jaccard
# similarity without carrying semantic meaning for memory deduplication.
_STOP_WORDS_2: frozenset[str] = frozenset(
    {
        "am",
        "an",
        "as",
        "at",
        "be",
        "by",
        "do",
        "he",
        "if",
        "in",
        "is",
        "it",
        "me",
        "my",
        "no",
        "of",
        "on",
        "or",
        "so",
        "to",
        "up",
        "us",
        "we",
    }
)


def _dedup_tokenize(text: str) -> set[str]:
    """Tokenize for dedup, keeping 2-char tokens (minus stopwords).

    Uses :func:`tokenize` with ``min_length=2`` so that short but
    meaningful tokens like ``go``, ``js``, ``ai``, ``ml`` are preserved,
    then removes common 2-letter English stopwords.
    """
    return tokenize(text, min_length=2) - _STOP_WORDS_2


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings.

    Uses :func:`_dedup_tokenize` (alpha-only tokens, len >= 2 minus
    stopwords) to preserve short but meaningful tokens that the default
    ``tokenize()`` (len >= 3) would discard.

    Args:
        a: First string.
        b: Second string.

    Returns:
        Jaccard similarity coefficient (0.0 to 1.0).
    """
    tokens_a = _dedup_tokenize(a)
    tokens_b = _dedup_tokenize(b)
    if not tokens_a and not tokens_b:
        return 1.0  # Both empty = identical
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def reconcile_fact(
    new_fact: str,
    existing_facts: list[MemoryEntry],
) -> tuple[str, str | None]:
    """Decide whether a new fact should be created, merged, or skipped.

    Compares the new fact content against all existing (non-superseded)
    facts using Jaccard token overlap. Returns the recommended action
    and an optional merge target ID.

    Thresholds:
      - >0.85 similarity: SKIP (near-duplicate, don't store)
      - 0.6-0.85 similarity: MERGE (update the existing fact)
      - <0.6 similarity: CREATE (store as new fact)

    When multiple existing facts match, the one with the highest
    similarity is used as the merge/skip target.

    Args:
        new_fact: The content string of the new fact to evaluate.
        existing_facts: List of existing MemoryEntry objects to compare against.

    Returns:
        Tuple of (action, merge_target_id) where:
          - action is "CREATE", "SKIP", or "MERGE"
          - merge_target_id is the ID of the existing fact to merge into
            (None for CREATE, set for SKIP and MERGE)
    """
    best_similarity = 0.0
    best_match: MemoryEntry | None = None

    for fact in existing_facts:
        # Skip already-superseded facts
        if fact.superseded_by is not None:
            continue
        sim = _jaccard_similarity(new_fact, fact.content)
        if sim > best_similarity:
            best_similarity = sim
            best_match = fact

    if best_similarity > 0.85 and best_match is not None:
        return ("SKIP", best_match.id)

    if best_similarity >= 0.6 and best_match is not None:
        return ("MERGE", best_match.id)

    return ("CREATE", None)
