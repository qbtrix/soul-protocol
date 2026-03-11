# test_phase1_fixes.py — Tests for Phase 1 ablation fixes.
# Created: phase1-ablation-fixes — Covers significance gate short-message rejection,
#   mundane message rejection, BM25Index basic scoring, BM25SearchStrategy protocol
#   compliance, logarithmic bond growth rate, and bond ceiling behavior.

from __future__ import annotations

import pytest

from soul_protocol.runtime.bond import Bond
from soul_protocol.runtime.memory.attention import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    compute_significance,
    is_significant,
    overall_significance,
    select_top_k,
)
from soul_protocol.runtime.memory.search import BM25Index
from soul_protocol.runtime.memory.strategy import BM25SearchStrategy, SearchStrategy
from soul_protocol.runtime.types import Interaction, SignificanceScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_interaction(user_input: str, agent_output: str = "") -> Interaction:
    return Interaction(user_input=user_input, agent_output=agent_output)


# ---------------------------------------------------------------------------
# Fix 1: Significance gate rejects short messages
# ---------------------------------------------------------------------------


class TestSignificanceGateShortMessages:
    """Short messages (<20 tokens) get a -0.3 penalty."""

    def test_hello_rejected(self):
        """A bare 'hello' should never pass the significance gate."""
        interaction = make_interaction("hello", "hi there")
        score = compute_significance(interaction, [], recent_contents=[])
        from soul_protocol.runtime.memory.search import tokenize

        tc = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        assert tc < 20  # confirms it's a short message
        assert is_significant(score, token_count=tc) is False

    def test_thanks_rejected(self):
        """'thanks' should not pass the significance gate."""
        interaction = make_interaction("thanks", "you're welcome")
        score = compute_significance(interaction, [], recent_contents=[])
        from soul_protocol.runtime.memory.search import tokenize

        tc = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        assert is_significant(score, token_count=tc) is False

    def test_short_message_penalty_applied(self):
        """overall_significance with low token count should be penalized."""
        score = SignificanceScore(novelty=1.0, emotional_intensity=0.0, goal_relevance=0.0)
        raw = overall_significance(score)
        penalized = overall_significance(score, token_count=5)
        assert penalized < raw
        assert penalized == pytest.approx(max(0.0, raw - 0.15))

    def test_long_message_no_penalty(self):
        """Messages with >=12 tokens should not receive a penalty."""
        score = SignificanceScore(novelty=1.0, emotional_intensity=0.0, goal_relevance=0.0)
        raw = overall_significance(score)
        no_penalty = overall_significance(score, token_count=15)
        assert no_penalty == raw


# ---------------------------------------------------------------------------
# Fix 1: Significance gate rejects mundane messages
# ---------------------------------------------------------------------------


class TestSignificanceGateMundane:
    """Mundane interactions with no emotion or goal relevance are rejected."""

    def test_mundane_weather_rejected(self):
        """A plain factual question should fail the raised threshold."""
        interaction = make_interaction(
            "What is the weather like today?",
            "It looks sunny outside.",
        )
        score = compute_significance(interaction, [], recent_contents=[])
        from soul_protocol.runtime.memory.search import tokenize

        tc = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        assert is_significant(score, token_count=tc) is False

    def test_emotional_interaction_passes(self):
        """An emotionally charged, substantive interaction should pass."""
        interaction = make_interaction(
            "I am absolutely thrilled about the breakthrough we made today in the machine learning project after months of hard work and dedication",
            "That is truly wonderful news! Your persistence and effort have clearly paid off in a meaningful way.",
        )
        score = compute_significance(interaction, [], recent_contents=[])
        from soul_protocol.runtime.memory.search import tokenize

        tc = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        assert is_significant(score, token_count=tc) is True


# ---------------------------------------------------------------------------
# Fix 1: select_top_k batch filter
# ---------------------------------------------------------------------------


class TestSelectTopK:
    """select_top_k marks only the top fraction of a batch."""

    def test_selects_top_half(self):
        scores = [0.9, 0.3, 0.7, 0.1]
        selected = select_top_k(scores, k_ratio=0.5)
        assert selected == [True, False, True, False]

    def test_empty_scores(self):
        assert select_top_k([]) == []

    def test_single_element(self):
        assert select_top_k([0.5], k_ratio=0.5) == [True]

    def test_all_same_scores(self):
        """When all scores are equal, select top k entries."""
        result = select_top_k([0.5, 0.5, 0.5, 0.5], k_ratio=0.5)
        assert sum(result) == 2


# ---------------------------------------------------------------------------
# Fix 2: BM25Index basic scoring
# ---------------------------------------------------------------------------


class TestBM25Index:
    """BM25Index provides term-frequency-saturated scoring."""

    def test_matching_term_scores_higher(self):
        """A document containing the query term should score higher than one that doesn't."""
        idx = BM25Index()
        idx.add("doc1", "Python is a versatile programming language")
        idx.add("doc2", "Java is used for enterprise applications")

        score_python = idx.score("python", "doc1")
        score_java = idx.score("python", "doc2")

        assert score_python > 0
        assert score_java == 0 or score_python > score_java

    def test_search_returns_ranked(self):
        """search() returns documents ranked by BM25 score."""
        idx = BM25Index()
        idx.add("d1", "Python programming language development")
        idx.add("d2", "Java enterprise application server")
        idx.add("d3", "Python machine learning artificial intelligence")

        results = idx.search("Python development", limit=10)
        assert len(results) >= 1
        # d1 should rank highest (both terms present)
        assert results[0][0] == "d1"

    def test_idf_weighting(self):
        """Rare terms should score higher than common terms (IDF effect)."""
        idx = BM25Index()
        idx.add("d1", "the cat sat on the mat with the dog")
        idx.add("d2", "the dog ran around the park with the cat")
        idx.add("d3", "a unique platypus appeared suddenly")

        # "platypus" appears in only 1 doc — higher IDF
        # "cat" appears in 2 docs — lower IDF
        score_rare = idx.score("platypus", "d3")
        score_common = idx.score("cat", "d1")
        assert score_rare > score_common

    def test_corpus_size(self):
        idx = BM25Index()
        assert idx.corpus_size == 0
        idx.add("d1", "hello world")
        assert idx.corpus_size == 1

    def test_remove(self):
        idx = BM25Index()
        idx.add("d1", "Python programming")
        idx.remove("d1")
        assert idx.corpus_size == 0
        assert idx.score("python", "d1") == 0.0


# ---------------------------------------------------------------------------
# Fix 2: BM25SearchStrategy implements SearchStrategy
# ---------------------------------------------------------------------------


class TestBM25SearchStrategy:
    """BM25SearchStrategy conforms to SearchStrategy protocol."""

    def test_implements_protocol(self):
        strategy = BM25SearchStrategy()
        assert isinstance(strategy, SearchStrategy)

    def test_score_returns_normalized(self):
        """score() returns a value between 0 and 1."""
        strategy = BM25SearchStrategy()
        result = strategy.score("python programming", "Python is a great programming language")
        assert 0.0 <= result <= 1.0

    def test_score_no_match_low(self):
        """Unrelated query and content should score near zero."""
        strategy = BM25SearchStrategy()
        result = strategy.score("quantum physics", "baking chocolate cake recipe")
        assert result < 0.1


# ---------------------------------------------------------------------------
# Fix 3: Logarithmic bond growth
# ---------------------------------------------------------------------------


class TestLogarithmicBondGrowth:
    """Bond growth follows a logarithmic curve (diminishing returns)."""

    def test_growth_rate_at_90(self):
        """At bond=90, growth per interaction should be < 0.15."""
        bond = Bond(bond_strength=90.0)
        before = bond.bond_strength
        bond.strengthen(1.0)
        gain = bond.bond_strength - before
        assert gain < 0.15
        # Exact: 1.0 * (10/100) = 0.1
        assert gain == pytest.approx(0.1)

    def test_does_not_reach_100_in_100_interactions(self):
        """Starting from 50, 100 default strengthen() calls should not reach 100."""
        bond = Bond(bond_strength=50.0)
        for _ in range(100):
            bond.strengthen()
        assert bond.bond_strength < 100.0
        assert bond.interaction_count == 100

    def test_growth_slows_over_time(self):
        """Each successive strengthen() call should produce less gain."""
        bond = Bond(bond_strength=50.0)
        gains = []
        for _ in range(10):
            before = bond.bond_strength
            bond.strengthen()
            gains.append(bond.bond_strength - before)

        # Each gain should be strictly less than the previous
        for i in range(1, len(gains)):
            assert gains[i] < gains[i - 1]

    def test_weaken_still_linear(self):
        """Weaken should remain linear (sharp) — unchanged from before."""
        bond = Bond(bond_strength=80.0)
        bond.weaken(5.0)
        assert bond.bond_strength == 75.0
