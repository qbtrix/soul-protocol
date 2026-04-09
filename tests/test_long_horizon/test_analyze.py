# test_analyze.py — Tests for long-horizon analysis module.
# Created: 2026-03-11
# Given mock data, validates that the analyzer produces correct stats,
# summary tables, pairwise comparisons, and markdown report.

from __future__ import annotations

import pytest

from research.long_horizon.analyze import (
    LongHorizonAnalyzer,
    _effect_label,
    cohens_d,
)
from research.long_horizon.runner import (
    ConditionResult,
    ConditionType,
    LongHorizonResults,
    ScenarioResults,
)


def _make_mock_results() -> LongHorizonResults:
    """Create mock results with known values for deterministic testing."""
    results = LongHorizonResults()

    # Scenario 1: Full Soul does well, others less so
    sr1 = ScenarioResults(scenario_id="test_1", scenario_name="Test Scenario 1")
    sr1.condition_results[ConditionType.FULL_SOUL] = ConditionResult(
        condition=ConditionType.FULL_SOUL,
        scenario_id="test_1",
        total_turns=100,
        recall_hits=8,
        recall_misses=2,
        total_memories=40,
        bond_strength=0.75,
    )
    sr1.condition_results[ConditionType.RAG_ONLY] = ConditionResult(
        condition=ConditionType.RAG_ONLY,
        scenario_id="test_1",
        total_turns=100,
        recall_hits=5,
        recall_misses=5,
        total_memories=100,
        bond_strength=0.0,
    )
    sr1.condition_results[ConditionType.PERSONALITY_ONLY] = ConditionResult(
        condition=ConditionType.PERSONALITY_ONLY,
        scenario_id="test_1",
        total_turns=100,
        recall_hits=0,
        recall_misses=10,
        total_memories=0,
        bond_strength=0.0,
    )
    sr1.condition_results[ConditionType.BARE_BASELINE] = ConditionResult(
        condition=ConditionType.BARE_BASELINE,
        scenario_id="test_1",
        total_turns=100,
        recall_hits=0,
        recall_misses=10,
        total_memories=0,
        bond_strength=0.0,
    )
    results.scenario_results.append(sr1)

    # Scenario 2: Similar pattern, different numbers
    sr2 = ScenarioResults(scenario_id="test_2", scenario_name="Test Scenario 2")
    sr2.condition_results[ConditionType.FULL_SOUL] = ConditionResult(
        condition=ConditionType.FULL_SOUL,
        scenario_id="test_2",
        total_turns=150,
        recall_hits=12,
        recall_misses=3,
        total_memories=55,
        bond_strength=0.85,
    )
    sr2.condition_results[ConditionType.RAG_ONLY] = ConditionResult(
        condition=ConditionType.RAG_ONLY,
        scenario_id="test_2",
        total_turns=150,
        recall_hits=6,
        recall_misses=9,
        total_memories=150,
        bond_strength=0.0,
    )
    sr2.condition_results[ConditionType.PERSONALITY_ONLY] = ConditionResult(
        condition=ConditionType.PERSONALITY_ONLY,
        scenario_id="test_2",
        total_turns=150,
        recall_hits=0,
        recall_misses=15,
        total_memories=0,
        bond_strength=0.0,
    )
    sr2.condition_results[ConditionType.BARE_BASELINE] = ConditionResult(
        condition=ConditionType.BARE_BASELINE,
        scenario_id="test_2",
        total_turns=150,
        recall_hits=0,
        recall_misses=15,
        total_memories=0,
        bond_strength=0.0,
    )
    results.scenario_results.append(sr2)

    return results


class TestCohensD:
    """Tests for the cohens_d statistical function."""

    def test_identical_groups(self):
        d = cohens_d([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert d == pytest.approx(0.0)

    def test_different_groups(self):
        d = cohens_d([10.0, 11.0, 12.0], [1.0, 2.0, 3.0])
        assert d > 0, "Higher group should produce positive d"

    def test_empty_groups(self):
        assert cohens_d([], [1.0, 2.0]) == 0.0
        assert cohens_d([1.0, 2.0], []) == 0.0
        assert cohens_d([], []) == 0.0

    def test_single_element(self):
        # With single elements, variance is 0, so d should be 0
        d = cohens_d([5.0], [3.0])
        assert d == 0.0

    def test_large_effect(self):
        d = cohens_d([100.0, 101.0, 102.0], [0.0, 1.0, 2.0])
        assert abs(d) > 0.8, "Should be a large effect"


class TestEffectLabel:
    """Tests for effect size labeling."""

    def test_negligible(self):
        assert _effect_label(0.1) == "negligible"

    def test_small(self):
        assert _effect_label(0.3) == "small"

    def test_medium(self):
        assert _effect_label(0.6) == "medium"

    def test_large(self):
        assert _effect_label(1.0) == "large"

    def test_negative_large(self):
        assert _effect_label(-1.0) == "large"


class TestLongHorizonAnalyzer:
    """Tests for the analyzer with mock data."""

    def test_summary_table_has_all_conditions(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        summary = analyzer.summary_table()

        conditions = [s["condition"] for s in summary]
        assert ConditionType.FULL_SOUL in conditions
        assert ConditionType.RAG_ONLY in conditions
        assert ConditionType.BARE_BASELINE in conditions

    def test_summary_table_recall_precision(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        summary = analyzer.summary_table()

        full_soul = next(s for s in summary if s["condition"] == ConditionType.FULL_SOUL)
        # Scenario 1: 8/10 = 0.8, Scenario 2: 12/15 = 0.8
        assert full_soul["recall_precision_mean"] == pytest.approx(0.8)

        rag = next(s for s in summary if s["condition"] == ConditionType.RAG_ONLY)
        # Scenario 1: 5/10 = 0.5, Scenario 2: 6/15 = 0.4
        assert rag["recall_precision_mean"] == pytest.approx(0.45)

    def test_summary_table_memory_efficiency(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        summary = analyzer.summary_table()

        full_soul = next(s for s in summary if s["condition"] == ConditionType.FULL_SOUL)
        # Scenario 1: 40/100 = 0.4, Scenario 2: 55/150 ≈ 0.367
        expected = (0.4 + 55 / 150) / 2
        assert full_soul["memory_efficiency_mean"] == pytest.approx(expected, rel=0.01)

        rag = next(s for s in summary if s["condition"] == ConditionType.RAG_ONLY)
        # RAG stores everything: efficiency = 1.0 for both
        assert rag["memory_efficiency_mean"] == pytest.approx(1.0)

    def test_summary_table_bond_strength(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        summary = analyzer.summary_table()

        full_soul = next(s for s in summary if s["condition"] == ConditionType.FULL_SOUL)
        # (0.75 + 0.85) / 2 = 0.80
        assert full_soul["bond_strength_mean"] == pytest.approx(0.8)

    def test_pairwise_comparisons_exist(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        comparisons = analyzer.pairwise_comparisons()

        assert len(comparisons) > 0
        # Should compare Full Soul vs 3 other conditions, 4 metrics each = 12
        assert len(comparisons) == 12

    def test_pairwise_full_soul_vs_rag_recall(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        comparisons = analyzer.pairwise_comparisons()

        recall_vs_rag = next(
            c
            for c in comparisons
            if c["condition_b"] == ConditionType.RAG_ONLY and c["metric"] == "Recall Precision"
        )
        # Full Soul: 0.8, RAG: 0.45 => delta = +0.35
        assert recall_vs_rag["delta"] == pytest.approx(0.35)
        assert recall_vs_rag["soul_mean"] > recall_vs_rag["other_mean"]

    def test_pairwise_full_soul_vs_bare(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        comparisons = analyzer.pairwise_comparisons()

        recall_vs_bare = next(
            c
            for c in comparisons
            if c["condition_b"] == ConditionType.BARE_BASELINE and c["metric"] == "Recall Precision"
        )
        assert recall_vs_bare["delta"] == pytest.approx(0.8)

    def test_per_scenario_breakdown(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        breakdown = analyzer.per_scenario_breakdown()

        assert len(breakdown) == 2
        assert breakdown[0]["scenario"] == "test_1"
        assert breakdown[1]["scenario"] == "test_2"

    def test_generate_report_is_markdown(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        report = analyzer.generate_report()

        assert isinstance(report, str)
        assert "# Long-Horizon Ablation Study Results" in report
        assert "## Summary by Condition" in report
        assert "## Full Soul vs Others" in report
        assert "## Per-Scenario Breakdown" in report
        assert "## Key Findings" in report

    def test_report_contains_condition_labels(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        report = analyzer.generate_report()

        assert "Full Soul" in report
        assert "RAG Only" in report
        assert "Bare Baseline" in report

    def test_report_contains_numeric_data(self):
        results = _make_mock_results()
        analyzer = LongHorizonAnalyzer(results)
        report = analyzer.generate_report()

        # Should contain formatted numbers
        assert "0.800" in report or "0.80" in report  # recall precision
        assert "0.000" in report or "0.00" in report  # bare baseline recall


class TestEdgeCases:
    """Test analyzer with edge case data."""

    def test_empty_results(self):
        results = LongHorizonResults()
        analyzer = LongHorizonAnalyzer(results)
        summary = analyzer.summary_table()
        assert summary == []

    def test_single_scenario(self):
        results = LongHorizonResults()
        sr = ScenarioResults(scenario_id="single", scenario_name="Single")
        sr.condition_results[ConditionType.FULL_SOUL] = ConditionResult(
            condition=ConditionType.FULL_SOUL,
            scenario_id="single",
            total_turns=50,
            recall_hits=5,
            recall_misses=5,
            total_memories=20,
        )
        results.scenario_results.append(sr)
        analyzer = LongHorizonAnalyzer(results)

        summary = analyzer.summary_table()
        assert len(summary) == 1

    def test_report_with_single_condition(self):
        """Report should work even with only one condition (no pairwise)."""
        results = LongHorizonResults()
        sr = ScenarioResults(scenario_id="single", scenario_name="Single")
        sr.condition_results[ConditionType.RAG_ONLY] = ConditionResult(
            condition=ConditionType.RAG_ONLY,
            scenario_id="single",
            total_turns=50,
            recall_hits=3,
            recall_misses=7,
            total_memories=50,
        )
        results.scenario_results.append(sr)
        analyzer = LongHorizonAnalyzer(results)

        # Should not crash
        report = analyzer.generate_report()
        assert "RAG Only" in report
