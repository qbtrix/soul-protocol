# tests/test_memory/test_dedup.py — Tests for the memory deduplication pipeline.
# Created: 2026-03-13 — Verifies:
#   - Jaccard similarity with synonym expansion catches synonym-variant duplicates
#   - reconcile_fact returns correct action (CREATE/SKIP/MERGE) for various inputs
#   - Edge cases: empty strings, single-token facts, no synonym overlap
# Updated: 2026-03-20 — Adjusted for asymmetric synonym expansion (only existing
#   fact is expanded). Added false-positive regression tests.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.dedup import _jaccard_similarity, reconcile_fact
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
# _jaccard_similarity — synonym-aware token overlap
# ===========================================================================


class TestJaccardSimilarity:
    """_jaccard_similarity should use synonym expansion for fuzzy matching."""

    def test_identical_strings(self):
        """Identical strings should return 1.0."""
        assert _jaccard_similarity("user likes python", "user likes python") == 1.0

    def test_completely_different_strings(self):
        """Strings with no token overlap should return 0.0."""
        assert _jaccard_similarity("apple banana cherry", "xylophone zebra quantum") == 0.0

    def test_both_empty(self):
        """Two empty strings should return 1.0 (both empty = identical)."""
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty(self):
        """One empty string should return 0.0."""
        assert _jaccard_similarity("hello world test", "") == 0.0
        assert _jaccard_similarity("", "hello world test") == 0.0

    def test_synonym_variant_bug_error(self):
        """'bug' and 'error' are synonyms — facts using them should have high similarity."""
        sim = _jaccard_similarity(
            "User reported a bug in the login flow",
            "User reported an error in the authentication flow",
        )
        # Asymmetric expansion: only b is expanded, so bug/login in a match
        # against expanded error→{error,bug,exception} and authentication→{auth,login,...} in b.
        # Score lands in MERGE range, not SKIP — this is correct and avoids false positives.
        assert sim >= 0.6, f"Expected >=0.6 (MERGE range), got {sim}"

    def test_synonym_variant_testing_frameworks(self):
        """'pytest' and 'unittest' are synonyms — testing preference facts should merge."""
        sim = _jaccard_similarity(
            "User prefers testing with pytest framework",
            "User prefers testing with unittest framework",
        )
        # pytest↔unittest↔test↔testing are in the same synonym group
        assert sim > 0.6, f"Expected >0.6 (MERGE range), got {sim}"

    def test_synonym_variant_deploy_shipping(self):
        """'deploy' and 'shipping' are synonyms — should boost similarity."""
        sim = _jaccard_similarity(
            "Team uses automated deploy pipeline",
            "Team uses automated shipping pipeline",
        )
        assert sim > 0.6, f"Expected >0.6 (MERGE range), got {sim}"

    def test_no_synonym_overlap_stays_low(self):
        """Unrelated facts should remain low similarity even with synonym expansion."""
        sim = _jaccard_similarity(
            "User enjoys hiking on weekends",
            "The database migration failed yesterday",
        )
        assert sim < 0.3, f"Expected <0.3 (CREATE range), got {sim}"

    def test_partial_overlap_without_synonyms(self):
        """Facts sharing some words but no synonym link should reflect actual overlap."""
        sim = _jaccard_similarity(
            "User likes reading books about history",
            "User likes watching movies about science",
        )
        # Shared: {user, likes, about} — no synonym expansion affects these
        assert 0.0 < sim < 0.6


# ===========================================================================
# reconcile_fact — CREATE / SKIP / MERGE decisions
# ===========================================================================


class TestReconcileFact:
    """reconcile_fact should return correct actions using synonym-aware similarity."""

    def test_create_when_no_existing_facts(self):
        """With no existing facts, always CREATE."""
        action, target = reconcile_fact("User knows Python", [])
        assert action == "CREATE"
        assert target is None

    def test_skip_near_duplicate(self):
        """Near-identical facts should SKIP."""
        existing = [_make_entry("User likes working with Python")]
        action, target = reconcile_fact("User likes working with Python", existing)
        assert action == "SKIP"
        assert target == "existing-1"

    def test_merge_synonym_duplicate(self):
        """Facts that are duplicates via synonyms should MERGE (asymmetric expansion)."""
        existing = [_make_entry("User reported a bug in the login module")]
        action, target = reconcile_fact(
            "User reported an error in the authentication module",
            existing,
        )
        # bug↔error, login↔authentication — asymmetric expansion catches the overlap
        # but scores in MERGE range rather than SKIP (which avoids false positives)
        assert action == "MERGE", f"Expected MERGE, got {action}"
        assert target == "existing-1"

    def test_merge_related_fact(self):
        """Facts with moderate overlap should MERGE."""
        existing = [_make_entry(
            "User works on the deployment pipeline for their team", "e1",
        )]
        action, target = reconcile_fact(
            "User works on the shipping pipeline for their project",
            existing,
        )
        # deploy↔deployment↔shipping are synonyms, pushes into MERGE range
        assert action == "MERGE"
        assert target == "e1"

    def test_create_unrelated_fact(self):
        """Completely unrelated facts should CREATE."""
        existing = [_make_entry("User enjoys hiking on weekends")]
        action, target = reconcile_fact(
            "The database schema needs a migration",
            existing,
        )
        assert action == "CREATE"
        assert target is None

    def test_skips_superseded_facts(self):
        """Facts with superseded_by set should be ignored during comparison."""
        superseded = _make_entry("User likes Python", "old-1")
        superseded.superseded_by = "newer-1"
        existing = [superseded]
        action, target = reconcile_fact("User likes Python", existing)
        # The only existing fact is superseded, so nothing to compare against
        assert action == "CREATE"
        assert target is None

    def test_picks_highest_similarity_match(self):
        """When multiple existing facts match, the best one is used."""
        existing = [
            _make_entry("User enjoys cooking Italian food", "e1"),
            _make_entry("User enjoys cooking Thai food", "e2"),
        ]
        action, target = reconcile_fact(
            "User enjoys cooking Thai dishes",
            existing,
        )
        # "Thai food" vs "Thai dishes" should match e2 more closely
        assert target == "e2"


# ===========================================================================
# False-positive regression tests — asymmetric expansion guard
# ===========================================================================


class TestNoFalsePositives:
    """Verify that asymmetric expansion does not inflate scores for unrelated facts."""

    def test_no_false_positive_different_synonym_groups(self):
        """Facts using different words from the same synonym groups are still distinct."""
        sim = _jaccard_similarity(
            "server configuration needed",
            "backend settings required",
        )
        assert sim < 0.6, f"Expected CREATE (< 0.6), got {sim}"

    def test_no_false_positive_auth_config_overlap(self):
        """Synonym-rich but genuinely different facts should not merge."""
        sim = _jaccard_similarity(
            "authentication service config",
            "login settings backend",
        )
        assert sim < 0.6, f"Expected CREATE (< 0.6), got {sim}"

    def test_no_false_positive_async_function(self):
        """Different synonym-group words should not inflate to MERGE range."""
        sim = _jaccard_similarity(
            "async function implementation",
            "asynchronous method code",
        )
        assert sim < 0.6, f"Expected CREATE (< 0.6), got {sim}"
