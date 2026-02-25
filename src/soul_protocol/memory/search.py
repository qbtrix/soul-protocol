# memory/search.py — Token-overlap relevance scoring for memory search.
# Updated: 2026-02-25 — Improved tokenize() to strip non-alpha characters from
#   within tokens (not just edges), preventing code snippets from creating junk
#   domain names like "os.environ.get('key". Added _ALPHA_RE for robust cleaning.
# Created: 2026-02-22 — Replaces simple substring matching with token-based
# scoring. Provides tokenize() and relevance_score() used by all memory stores.

from __future__ import annotations

import re

# Keep only alphabetic characters — strips digits, punctuation, code artifacts
_ALPHA_RE = re.compile(r"[^a-z]+")


def tokenize(text: str) -> set[str]:
    """Split text into lowercase alphabetic tokens, removing short words.

    Strips all non-alphabetic characters (punctuation, digits, code syntax)
    and discards any resulting token shorter than 3 characters.

    This prevents code snippets like ``os.environ.get('KEY')`` or
    ``app.config['DEBUG']`` from producing noisy tokens — only clean
    English words survive.

    Args:
        text: The input string to tokenize.

    Returns:
        A set of cleaned, lowercased alpha-only tokens with len >= 3.
    """
    # Split on whitespace, then strip non-alpha chars entirely
    words = (_ALPHA_RE.sub("", w) for w in text.lower().split())
    return {w for w in words if len(w) >= 3}


def relevance_score(query: str, content: str) -> float:
    """Score 0.0-1.0 based on token overlap between query and content.

    Measures what fraction of query tokens appear in the content.
    A score of 1.0 means every query token was found in the content.
    A score of 0.0 means no overlap at all.

    Args:
        query: The search query string.
        content: The content string to score against.

    Returns:
        Float between 0.0 and 1.0 representing relevance.
    """
    query_tokens = tokenize(query)
    content_tokens = tokenize(content)
    if not query_tokens:
        return 0.0
    overlap = query_tokens & content_tokens
    return len(overlap) / len(query_tokens)
