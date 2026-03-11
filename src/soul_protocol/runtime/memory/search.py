# memory/search.py — Token-overlap and BM25 relevance scoring for memory search.
# Updated: phase1-ablation-fixes — Added BM25Index class for term-frequency-saturated,
#   length-normalized retrieval scoring. BM25 uses IDF weighting, k1=1.2, b=0.75.
#   Token-overlap relevance_score() kept as fallback.
# Updated: 2026-03-02 — Fixed tokenizer to split on /, _, -, . in addition to
#   whitespace so file paths and identifiers are searchable by component (issue #11).
#   Added synonym/alias expansion layer for improved recall on common programming
#   terms like database/sql/db, javascript/js, python/py, etc. (issue #10).
# Updated: 2026-02-25 — Improved tokenize() to strip non-alpha characters from
#   within tokens (not just edges), preventing code snippets from creating junk
#   domain names like "os.environ.get('key". Added _ALPHA_RE for robust cleaning.
# Created: 2026-02-22 — Replaces simple substring matching with token-based
# scoring. Provides tokenize() and relevance_score() used by all memory stores.

from __future__ import annotations

import math
import re
from collections import Counter

# Keep only alphabetic characters — strips digits, punctuation, code artifacts
_ALPHA_RE = re.compile(r"[^a-z]+")

# Split on whitespace plus common identifier/path separators: / _ - .
_SPLIT_RE = re.compile(r"[\s/_.\\-]+")

# ---------------------------------------------------------------------------
# Synonym / alias groups for improved recall (issue #10)
# ---------------------------------------------------------------------------
# Each tuple is a group of related terms. When any member appears in a token
# set, all other members are added so that token-overlap can match synonyms.
# Keep this small and focused on common programming/tech terms.

_SYNONYM_GROUPS: list[tuple[str, ...]] = [
    ("database", "sql", "postgresql", "postgres", "mysql", "sqlite", "mongo", "mongodb"),
    ("javascript", "typescript"),
    ("python", "pip"),
    ("frontend", "client", "browser"),
    ("backend", "server"),
    ("api", "rest", "endpoint"),
    ("test", "testing", "pytest", "unittest"),
    ("deploy", "deployment", "shipping"),
    ("container", "docker", "kubernetes"),
    ("auth", "authentication", "login"),
    ("config", "configuration", "settings"),
    ("error", "exception", "bug"),
    ("async", "asynchronous", "await"),
    ("func", "function", "method"),
    ("repo", "repository", "git"),
    ("dependency", "dependencies", "package", "packages"),
    ("http", "https", "request", "response"),
    ("cli", "command", "terminal"),
]

# Build a lookup: token → frozenset of all synonyms (including itself)
_SYNONYM_MAP: dict[str, frozenset[str]] = {}
for _group in _SYNONYM_GROUPS:
    _fset = frozenset(_group)
    for _term in _group:
        # A term may appear in multiple groups — merge them
        if _term in _SYNONYM_MAP:
            _fset = _fset | _SYNONYM_MAP[_term]
    # Re-assign the merged set to every term in the merged group
    for _term in _fset:
        _SYNONYM_MAP[_term] = _fset


def _expand_synonyms(tokens: set[str]) -> set[str]:
    """Expand a token set with synonyms from ``_SYNONYM_MAP``.

    For each token that appears in the synonym map, all members of its
    synonym group are added to the returned set.  Tokens without synonyms
    pass through unchanged.

    Args:
        tokens: The original token set.

    Returns:
        A new set containing the originals plus any synonym expansions.
    """
    expanded = set(tokens)
    for tok in tokens:
        group = _SYNONYM_MAP.get(tok)
        if group is not None:
            expanded |= group
    return expanded


def tokenize(text: str) -> set[str]:
    """Split text into lowercase alphabetic tokens, removing short words.

    Splits on whitespace **and** common separators (``/``, ``_``, ``-``,
    ``.``) so that file paths like ``app/routes/handler.py`` and snake_case
    identifiers like ``user_session_token`` produce individual searchable
    tokens.

    Strips all non-alphabetic characters (punctuation, digits, code syntax)
    and discards any resulting token shorter than 3 characters.

    Args:
        text: The input string to tokenize.

    Returns:
        A set of cleaned, lowercased alpha-only tokens with len >= 3.
    """
    # Split on whitespace + path/identifier separators, then strip non-alpha
    words = (_ALPHA_RE.sub("", w) for w in _SPLIT_RE.split(text.lower()))
    return {w for w in words if len(w) >= 3}


def relevance_score(query: str, content: str) -> float:
    """Score 0.0-1.0 based on token overlap between query and content.

    Measures what fraction of query tokens appear in the content, after
    expanding both sides with programming-domain synonyms.  A score of
    1.0 means every query token (or a synonym) was found in the content.
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
    expanded_content = _expand_synonyms(content_tokens)
    overlap = query_tokens & expanded_content
    return len(overlap) / len(query_tokens)


# ---------------------------------------------------------------------------
# BM25 Index — term-frequency-saturated, length-normalized scoring
# ---------------------------------------------------------------------------

# BM25 parameters (Okapi defaults)
_BM25_K1: float = 1.2
_BM25_B: float = 0.75


class BM25Index:
    """Pure-Python BM25 index for memory retrieval.

    Provides term-frequency saturation and document-length normalization
    that raw token overlap lacks.  Synonym expansion is applied before
    indexing and querying so the existing synonym layer is preserved.

    Usage::

        idx = BM25Index()
        idx.add("doc1", "Python is a great language")
        idx.add("doc2", "Java is also popular")
        results = idx.search("python programming", limit=5)
    """

    def __init__(self) -> None:
        # doc_id -> {term: frequency}
        self._doc_tf: dict[str, Counter[str]] = {}
        # doc_id -> document length (number of tokens)
        self._doc_len: dict[str, int] = {}
        # term -> set of doc_ids containing it
        self._inverted: dict[str, set[str]] = {}
        # Running average document length
        self._total_tokens: int = 0

    @property
    def corpus_size(self) -> int:
        """Number of indexed documents."""
        return len(self._doc_tf)

    @property
    def avg_doc_len(self) -> float:
        """Average document length across the corpus."""
        if not self._doc_tf:
            return 0.0
        return self._total_tokens / len(self._doc_tf)

    def add(self, doc_id: str, content: str) -> None:
        """Index a document (overwrites if doc_id already exists).

        Args:
            doc_id: Unique document identifier.
            content: Raw text content to index.
        """
        tokens = tokenize(content)
        expanded = _expand_synonyms(tokens)
        token_list = list(expanded)
        tf = Counter(token_list)

        # Remove old stats if overwriting
        if doc_id in self._doc_tf:
            self._remove(doc_id)

        self._doc_tf[doc_id] = tf
        self._doc_len[doc_id] = len(token_list)
        self._total_tokens += len(token_list)

        for term in tf:
            if term not in self._inverted:
                self._inverted[term] = set()
            self._inverted[term].add(doc_id)

    def _remove(self, doc_id: str) -> None:
        """Remove a document from the index (internal)."""
        old_tf = self._doc_tf.pop(doc_id, None)
        old_len = self._doc_len.pop(doc_id, 0)
        self._total_tokens -= old_len
        if old_tf:
            for term in old_tf:
                inv = self._inverted.get(term)
                if inv:
                    inv.discard(doc_id)
                    if not inv:
                        del self._inverted[term]

    def remove(self, doc_id: str) -> None:
        """Remove a document from the index.

        Args:
            doc_id: The document to remove.
        """
        self._remove(doc_id)

    def score(self, query: str, doc_id: str) -> float:
        """Compute BM25 score for a query against a specific document.

        Args:
            query: The search query.
            doc_id: The document to score against.

        Returns:
            BM25 score (higher = more relevant). Returns 0.0 if doc not found.
        """
        if doc_id not in self._doc_tf:
            return 0.0

        query_tokens = _expand_synonyms(tokenize(query))
        tf = self._doc_tf[doc_id]
        dl = self._doc_len[doc_id]
        avgdl = self.avg_doc_len or 1.0
        n_docs = self.corpus_size

        total = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            f = tf[term]
            n_containing = len(self._inverted.get(term, set()))
            # IDF with smoothing
            idf = math.log((n_docs - n_containing + 0.5) / (n_containing + 0.5) + 1.0)
            # BM25 term score
            numerator = f * (_BM25_K1 + 1.0)
            denominator = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avgdl)
            total += idf * numerator / denominator

        return total

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Search the corpus and return ranked results.

        Args:
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of (doc_id, score) tuples sorted by descending score.
        """
        scores: list[tuple[str, float]] = []
        for doc_id in self._doc_tf:
            s = self.score(query, doc_id)
            if s > 0:
                scores.append((doc_id, s))
        scores.sort(key=lambda x: -x[1])
        return scores[:limit]
