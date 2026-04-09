# analyze.py — Results analysis for long-horizon ablation study.
# Created: 2026-03-11
# Compares conditions across all scenarios, generates summary tables,
# calculates effect sizes (Cohen's d), and outputs markdown report.

from __future__ import annotations

import math
import statistics
from typing import Any

from .runner import ConditionType, LongHorizonResults

# ---------------------------------------------------------------------------
# Condition labels for human-readable output
# ---------------------------------------------------------------------------

CONDITION_LABELS = {
    ConditionType.FULL_SOUL: "Full Soul",
    ConditionType.RAG_ONLY: "RAG Only",
    ConditionType.PERSONALITY_ONLY: "Personality Only",
    ConditionType.BARE_BASELINE: "Bare Baseline",
}

CONDITION_ORDER = [
    ConditionType.BARE_BASELINE,
    ConditionType.PERSONALITY_ONLY,
    ConditionType.RAG_ONLY,
    ConditionType.FULL_SOUL,
]


# ---------------------------------------------------------------------------
# Statistical utilities
# ---------------------------------------------------------------------------


def cohens_d(group1: list[float], group2: list[float]) -> float:
    """Calculate Cohen's d effect size between two groups."""
    if not group1 or not group2:
        return 0.0
    n1, n2 = len(group1), len(group2)
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1 = statistics.variance(group1) if n1 > 1 else 0.0
    var2 = statistics.variance(group2) if n2 > 1 else 0.0
    denom = n1 + n2 - 2
    if denom <= 0:
        return 0.0
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / denom)
    if pooled_std == 0:
        return 0.0
    return (mean1 - mean2) / pooled_std


def _effect_label(d: float) -> str:
    """Human-readable effect size label."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    if abs_d < 0.5:
        return "small"
    if abs_d < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class LongHorizonAnalyzer:
    """Analyze long-horizon ablation results."""

    def __init__(self, results: LongHorizonResults) -> None:
        self.results = results
        self._rows = results.to_rows()

    def summary_table(self) -> list[dict[str, Any]]:
        """Generate summary table: one row per condition aggregated across scenarios."""
        by_condition: dict[str, list[dict]] = {}
        for row in self._rows:
            by_condition.setdefault(row["condition"], []).append(row)

        summary = []
        for cond in CONDITION_ORDER:
            rows = by_condition.get(cond, [])
            if not rows:
                continue

            precisions = [r["recall_precision"] for r in rows]
            efficiencies = [r["memory_efficiency"] for r in rows]
            memories = [r["total_memories"] for r in rows]
            bonds = [r["bond_strength"] for r in rows]

            summary.append(
                {
                    "condition": cond,
                    "label": CONDITION_LABELS.get(cond, cond),
                    "n_scenarios": len(rows),
                    "recall_precision_mean": statistics.mean(precisions),
                    "recall_precision_values": precisions,
                    "memory_efficiency_mean": statistics.mean(efficiencies),
                    "memory_efficiency_values": efficiencies,
                    "total_memories_mean": statistics.mean(memories),
                    "total_memories_values": memories,
                    "bond_strength_mean": statistics.mean(bonds),
                    "bond_strength_values": bonds,
                }
            )

        return summary

    def pairwise_comparisons(self) -> list[dict[str, Any]]:
        """Compare Full Soul vs every other condition."""
        summary = self.summary_table()
        full_soul_row = next(
            (s for s in summary if s["condition"] == ConditionType.FULL_SOUL),
            None,
        )
        if not full_soul_row:
            return []

        comparisons = []
        metrics = [
            ("recall_precision", "Recall Precision"),
            ("memory_efficiency", "Memory Efficiency"),
            ("total_memories", "Total Memories"),
            ("bond_strength", "Bond Strength"),
        ]

        for s in summary:
            if s["condition"] == ConditionType.FULL_SOUL:
                continue

            for metric_key, metric_label in metrics:
                soul_vals = full_soul_row[f"{metric_key}_values"]
                other_vals = s[f"{metric_key}_values"]

                d = cohens_d(soul_vals, other_vals)
                delta = full_soul_row[f"{metric_key}_mean"] - s[f"{metric_key}_mean"]

                comparisons.append(
                    {
                        "condition_a": ConditionType.FULL_SOUL,
                        "condition_b": s["condition"],
                        "metric": metric_label,
                        "cohens_d": d,
                        "effect_label": _effect_label(d),
                        "delta": delta,
                        "soul_mean": full_soul_row[f"{metric_key}_mean"],
                        "other_mean": s[f"{metric_key}_mean"],
                    }
                )

        return comparisons

    def per_scenario_breakdown(self) -> list[dict[str, Any]]:
        """Per-scenario comparison across conditions."""
        breakdown = []
        for sr in self.results.scenario_results:
            entry = {
                "scenario": sr.scenario_id,
                "scenario_name": sr.scenario_name,
            }
            for cond, cr in sr.condition_results.items():
                label = CONDITION_LABELS.get(cond, cond).replace(" ", "_").lower()
                entry[f"{label}_recall"] = cr.recall_precision
                entry[f"{label}_memories"] = cr.total_memories
                entry[f"{label}_efficiency"] = cr.memory_efficiency
                entry[f"{label}_bond"] = cr.bond_strength
            breakdown.append(entry)
        return breakdown

    def generate_report(self) -> str:
        """Generate a markdown report of the analysis."""
        sections: list[str] = []

        sections.append("# Long-Horizon Ablation Study Results")
        sections.append("")
        sections.append(
            "This report compares 4 ablation conditions across 100+ turn "
            "conversations to measure the impact of Soul Protocol's psychology "
            "stack at scale."
        )
        sections.append("")

        # Summary table
        sections.append("## Summary by Condition")
        sections.append("")
        summary = self.summary_table()
        sections.append(
            "| Condition | Scenarios | Recall Precision | Memory Efficiency | "
            "Total Memories | Bond Strength |"
        )
        sections.append(
            "|-----------|-----------|-----------------|-------------------|"
            "---------------|---------------|"
        )
        for s in summary:
            sections.append(
                f"| {s['label']} | {s['n_scenarios']} | "
                f"{s['recall_precision_mean']:.3f} | "
                f"{s['memory_efficiency_mean']:.3f} | "
                f"{s['total_memories_mean']:.1f} | "
                f"{s['bond_strength_mean']:.3f} |"
            )
        sections.append("")

        # Pairwise comparisons
        sections.append("## Full Soul vs Others (Effect Sizes)")
        sections.append("")
        comparisons = self.pairwise_comparisons()
        if comparisons:
            sections.append("| vs Condition | Metric | Delta | Cohen's d | Effect |")
            sections.append("|-------------|--------|-------|-----------|--------|")
            for c in comparisons:
                label_b = CONDITION_LABELS.get(c["condition_b"], c["condition_b"])
                delta_str = f"{c['delta']:+.3f}"
                sections.append(
                    f"| {label_b} | {c['metric']} | {delta_str} | "
                    f"{c['cohens_d']:.3f} | {c['effect_label']} |"
                )
        sections.append("")

        # Per-scenario breakdown
        sections.append("## Per-Scenario Breakdown")
        sections.append("")
        for sr in self.results.scenario_results:
            sections.append(f"### {sr.scenario_name}")
            sections.append("")
            sections.append("| Condition | Recall | Memories | Efficiency | Bond |")
            sections.append("|-----------|--------|----------|------------|------|")
            for cond in CONDITION_ORDER:
                cr = sr.condition_results.get(cond)
                if not cr:
                    continue
                label = CONDITION_LABELS.get(cond, cond)
                sections.append(
                    f"| {label} | {cr.recall_precision:.3f} | "
                    f"{cr.total_memories} | {cr.memory_efficiency:.3f} | "
                    f"{cr.bond_strength:.3f} |"
                )
            sections.append("")

            # Show missed recalls for full_soul to highlight gaps
            full_cr = sr.condition_results.get(ConditionType.FULL_SOUL)
            if full_cr:
                missed = [r for r in full_cr.recall_results if not r["hit"]]
                if missed:
                    sections.append(f"**Missed recalls (Full Soul):** {len(missed)}")
                    for m in missed[:5]:
                        sections.append(f"  - Q: {m['query']} (expected: {m['expected']})")
                    sections.append("")

        # Key findings
        sections.append("## Key Findings")
        sections.append("")
        if summary:
            full = next((s for s in summary if s["condition"] == ConditionType.FULL_SOUL), None)
            rag = next((s for s in summary if s["condition"] == ConditionType.RAG_ONLY), None)
            bare = next((s for s in summary if s["condition"] == ConditionType.BARE_BASELINE), None)

            if full and rag:
                recall_gap = full["recall_precision_mean"] - rag["recall_precision_mean"]
                eff_gap = rag["memory_efficiency_mean"] - full["memory_efficiency_mean"]
                sections.append(
                    f"- **Full Soul vs RAG Only recall gap:** {recall_gap:+.3f} "
                    f"(significance gating helps find buried facts)"
                )
                sections.append(
                    f"- **Memory efficiency advantage:** RAG stores {eff_gap:+.3f} more "
                    f"memories per turn (noise accumulation)"
                )
            if full and bare:
                sections.append(
                    f"- **Full Soul vs Bare Baseline recall gap:** "
                    f"{full['recall_precision_mean'] - bare['recall_precision_mean']:+.3f}"
                )
            if full:
                sections.append(
                    f"- **Bond strength after 100+ turns:** {full['bond_strength_mean']:.3f}"
                )
        sections.append("")

        return "\n".join(sections)
