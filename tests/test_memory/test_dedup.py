# tests/test_memory/test_dedup.py — Tests for the memory deduplication pipeline.
# Verifies:
#   - _dedup_tokenize preserves meaningful 2-char tokens and drops stopwords
#   - Jaccard similarity correctly distinguishes short-token facts (Go vs JS)
#   - reconcile_fact returns correct action (CREATE/SKIP/MERGE) for various inputs
#   - Edge cases: empty strings, single-token facts, short abbreviations

from __future__ import annotations

from soul_protocol.runtime.memory.dedup import (
    _dedup_tokenize,
    _jaccard_similarity,
    reconcile_fact,
)
from soul_protocol.runtime.types import MemoryEntry, MemoryType

# ===========================================================================
# Helpers
# ===========================================================================


def _make_entry(content: str, entry_id: str = "existing-1") -> MemoryEntry:
    """Create a minimal MemoryEntry for testing."""
    return MemoryEntry(
        id=entry_id,
        type=MemoryType.SEMANTIC,
        content=content,
    )


# ===========================================================================
# _dedup_tokenize — preserves 2-char tokens, drops stopwords
# ===========================================================================


class TestDedupTokenize:
    """_dedup_tokenize should keep meaningful 2-char tokens and drop stopwords."""

    def test_preserves_go(self):
        tokens = _dedup_tokenize("User knows Go")
        assert "go" in tokens

    def test_preserves_js(self):
        tokens = _dedup_tokenize("User knows JS")
        assert "js" in tokens

    def test_preserves_ai_ml(self):
        tokens = _dedup_tokenize("User prefers AI and ML tools")
        assert "ai" in tokens
        assert "ml" in tokens

    def test_preserves_ui_ux(self):
        tokens = _dedup_tokenize("experience with UI and UX design")
        assert "ui" in tokens
        assert "ux" in tokens

    def test_preserves_ci_cd(self):
        tokens = _dedup_tokenize("Set up CI/CD pipeline")
        assert "ci" in tokens
        assert "cd" in tokens

    def test_drops_stopwords(self):
        tokens = _dedup_tokenize("it is in an of or to do if by at on")
        assert len(tokens) == 0

    def test_drops_single_char(self):
        tokens = _dedup_tokenize("I use R and C")
        assert "i" not in tokens
        assert "r" not in tokens
        assert "c" not in tokens

    def test_keeps_longer_tokens_unchanged(self):
        tokens = _dedup_tokenize("User prefers Python")
        assert tokens == {"user", "prefers", "python"}


# ===========================================================================
# _jaccard_similarity — basic behavior
# ===========================================================================


class TestJaccardSimilarity:
    def test_identical_strings(self):
        assert _jaccard_similarity("user likes python", "user likes python") == 1.0

    def test_completely_different_strings(self):
        assert _jaccard_similarity("apple banana cherry", "xylophone zebra quantum") == 0.0

    def test_both_empty(self):
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty(self):
        assert _jaccard_similarity("hello world test", "") == 0.0
        assert _jaccard_similarity("", "hello world test") == 0.0

    def test_partial_overlap(self):
        sim = _jaccard_similarity(
            "User likes reading books about history",
            "User likes watching movies about science",
        )
        assert 0.0 < sim < 0.6


# ===========================================================================
# Short-token false-positive regression tests
# ===========================================================================


class TestShortTokenFalsePositives:
    """Verify that short distinguishing tokens prevent false-positive SKIP.

    Before the fix, all these pairs produced Jaccard = 1.0 and action = SKIP
    because the tokenizer dropped the only distinguishing word (len < 3).
    """

    def test_go_vs_js_not_skip(self):
        sim = _jaccard_similarity("User knows Go", "User knows JS")
        assert sim < 0.85, f"Expected < 0.85 (not SKIP), got {sim}"

    def test_go_vs_go_still_skip(self):
        sim = _jaccard_similarity("User knows Go", "User knows Go")
        assert sim > 0.85, f"Expected > 0.85 (SKIP), got {sim}"

    def test_ai_vs_ml_tools_not_skip(self):
        sim = _jaccard_similarity("User prefers AI tools", "User prefers ML tools")
        assert sim < 0.85, f"Expected < 0.85 (not SKIP), got {sim}"

    def test_ui_vs_ux_not_skip(self):
        sim = _jaccard_similarity(
            "User has experience with UI design",
            "User has experience with UX design",
        )
        assert sim < 0.85, f"Expected < 0.85 (not SKIP), got {sim}"

    def test_ci_vs_cd_not_skip(self):
        sim = _jaccard_similarity("Set up CI pipeline", "Set up CD pipeline")
        assert sim < 0.85, f"Expected < 0.85 (not SKIP), got {sim}"

    def test_go_api_vs_csharp_api_not_skip(self):
        sim = _jaccard_similarity(
            "Team uses Go for API development",
            "Team uses C# for API development",
        )
        assert sim < 0.85, f"Expected < 0.85 (not SKIP), got {sim}"


# ===========================================================================
# reconcile_fact — CREATE / SKIP / MERGE decisions
# ===========================================================================


class TestReconcileFact:
    def test_create_when_no_existing_facts(self):
        action, target = reconcile_fact("User knows Python", [])
        assert action == "CREATE"
        assert target is None

    def test_skip_near_duplicate(self):
        existing = [_make_entry("User likes working with Python")]
        action, target = reconcile_fact("User likes working with Python", existing)
        assert action == "SKIP"
        assert target == "existing-1"

    def test_create_unrelated_fact(self):
        existing = [_make_entry("User enjoys hiking on weekends")]
        action, target = reconcile_fact(
            "The database schema needs a migration",
            existing,
        )
        assert action == "CREATE"
        assert target is None

    def test_skips_superseded_facts(self):
        superseded = _make_entry("User likes Python", "old-1")
        superseded.superseded_by = "newer-1"
        existing = [superseded]
        action, target = reconcile_fact("User likes Python", existing)
        assert action == "CREATE"
        assert target is None

    def test_picks_highest_similarity_match(self):
        existing = [
            _make_entry("User enjoys cooking Italian food", "e1"),
            _make_entry("User enjoys cooking Thai food", "e2"),
        ]
        action, target = reconcile_fact(
            "User enjoys cooking Thai dishes",
            existing,
        )
        assert target == "e2"

    def test_reconcile_go_vs_js_not_skip(self):
        existing = [_make_entry("User knows Go")]
        action, _ = reconcile_fact("User knows JS", existing)
        assert action != "SKIP", f"Expected CREATE or MERGE, got {action}"

    def test_reconcile_go_vs_go_still_skip(self):
        existing = [_make_entry("User knows Go")]
        action, target = reconcile_fact("User knows Go", existing)
        assert action == "SKIP"
        assert target == "existing-1"

    def test_reconcile_ai_vs_ml_not_skip(self):
        existing = [_make_entry("User prefers AI tools")]
        action, _ = reconcile_fact("User prefers ML tools", existing)
        assert action != "SKIP", f"Expected CREATE or MERGE, got {action}"
