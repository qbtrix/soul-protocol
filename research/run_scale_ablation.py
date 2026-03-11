#!/usr/bin/env python3
# run_scale_ablation.py — Dedicated runner for the 1000-turn scale ablation study.
# Created: 2026-03-11
# Tests Soul Protocol's selective storage vs RAG at high turn counts.
# At 1000 turns: Soul gets 85% recall with 175 memories (0.19 recall/memory),
# RAG gets 100% recall with 1000 memories (0.04 recall/memory).
# Soul is 4.9x more memory-efficient. RAG's BM25 doesn't degrade at 1K docs
# but the storage cost is 5.7x higher. Crossover likely at 5-10K+ turns.
#
# Runs the marathon scenario through all 4 conditions (heuristic only, no API cost):
#   1. full_soul — Complete Soul Protocol pipeline
#   2. rag_only — Store every turn, recall via search
#   3. personality_only — OCEAN personality but no memory
#   4. bare_baseline — No memory, no personality
#
# Output: research/results/scale_ablation/
#   - results.json — Raw data
#   - report.md — Markdown analysis with recall-by-age breakdown
#   - summary.txt — Console-friendly summary

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Ensure both the project root (for `research` package) and src/ (for soul_protocol) are on path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from research.long_horizon.runner import (
    ALL_CONDITIONS,
    ConditionResult,
    ConditionType,
    LongHorizonRunner,
)
from research.long_horizon.scale_scenarios import generate_marathon_scenario


# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("research/results/scale_ablation")


# ---------------------------------------------------------------------------
# Recall-by-age analysis
# ---------------------------------------------------------------------------

# Fact age categories (mapped from test point descriptions)
AGE_CATEGORIES = {
    "callback_early": "Callback (turns 5-48)",
    "mid_range": "Mid-range (turns 75-250)",
    "preference": "Preferences (turns 275-500)",
    "professional": "Professional (turns 500-750)",
    "late_game": "Late-game (turns 750-960)",
    "synthesis": "Synthesis (cross-reference)",
}

AGE_ORDER = ["callback_early", "mid_range", "preference", "professional", "late_game", "synthesis"]


def _extract_category(description: str) -> str:
    """Extract age category from test point description."""
    for cat in AGE_CATEGORIES:
        if f"[{cat}]" in description:
            return cat
    return "unknown"


def _analyze_recall_by_age(
    condition_results: dict[str, ConditionResult],
) -> dict[str, dict[str, dict]]:
    """Break down recall hits/misses by fact age category for each condition.

    Returns: {condition: {category: {"hits": N, "misses": N, "total": N, "rate": float}}}
    """
    analysis: dict[str, dict[str, dict]] = {}

    for cond, cr in condition_results.items():
        by_cat: dict[str, dict] = defaultdict(lambda: {"hits": 0, "misses": 0})
        for rr in cr.recall_results:
            cat = _extract_category(rr.get("description", ""))
            if rr["hit"]:
                by_cat[cat]["hits"] += 1
            else:
                by_cat[cat]["misses"] += 1

        # Calculate rates
        for cat in by_cat:
            total = by_cat[cat]["hits"] + by_cat[cat]["misses"]
            by_cat[cat]["total"] = total
            by_cat[cat]["rate"] = by_cat[cat]["hits"] / total if total > 0 else 0.0

        analysis[cond] = dict(by_cat)

    return analysis


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report(
    condition_results: dict[str, ConditionResult],
    age_analysis: dict[str, dict[str, dict]],
    duration: float,
) -> str:
    """Generate a markdown report for the scale ablation study."""
    lines: list[str] = []

    lines.append("# Scale Ablation Study: 1000-Turn Marathon")
    lines.append("")
    lines.append("**Hypothesis:** At 1000+ turns, RAG's recall degrades (BM25 gets noisier")
    lines.append("with more documents) while Soul's selective storage keeps the corpus lean")
    lines.append("and recall stays stable.")
    lines.append("")
    lines.append(f"**Duration:** {duration:.1f}s")
    lines.append("")

    # --- Overall results table ---
    lines.append("## Overall Results")
    lines.append("")
    lines.append("| Condition | Recall Rate | Hits/Total | Memories Stored | Storage Ratio | Bond |")
    lines.append("|-----------|------------|------------|-----------------|---------------|------|")

    cond_order = [
        ConditionType.BARE_BASELINE,
        ConditionType.PERSONALITY_ONLY,
        ConditionType.RAG_ONLY,
        ConditionType.FULL_SOUL,
    ]
    cond_labels = {
        ConditionType.BARE_BASELINE: "Bare Baseline",
        ConditionType.PERSONALITY_ONLY: "Personality Only",
        ConditionType.RAG_ONLY: "RAG Only",
        ConditionType.FULL_SOUL: "Full Soul",
    }

    for cond in cond_order:
        cr = condition_results.get(cond)
        if not cr:
            continue
        total_tests = cr.recall_hits + cr.recall_misses
        recall_rate = cr.recall_precision * 100
        storage_ratio = cr.memory_efficiency
        lines.append(
            f"| {cond_labels[cond]} | {recall_rate:5.1f}% | "
            f"{cr.recall_hits}/{total_tests} | "
            f"{cr.total_memories} | {storage_ratio:.3f} | "
            f"{cr.bond_strength:.3f} |"
        )
    lines.append("")

    # --- Key comparison ---
    full_cr = condition_results.get(ConditionType.FULL_SOUL)
    rag_cr = condition_results.get(ConditionType.RAG_ONLY)

    if full_cr and rag_cr:
        lines.append("## Soul vs RAG at Scale")
        lines.append("")
        soul_rate = full_cr.recall_precision * 100
        rag_rate = rag_cr.recall_precision * 100
        soul_mems = full_cr.total_memories
        rag_mems = rag_cr.total_memories

        if soul_rate > rag_rate:
            verdict = f"Soul Protocol WINS by {soul_rate - rag_rate:.1f} percentage points"
        elif rag_rate > soul_rate:
            verdict = f"RAG wins by {rag_rate - soul_rate:.1f} percentage points"
        else:
            verdict = "Tied on recall rate"

        lines.append(f"- **Recall:** Soul {soul_rate:.1f}% vs RAG {rag_rate:.1f}% -> {verdict}")
        lines.append(f"- **Memories stored:** Soul {soul_mems} vs RAG {rag_mems} "
                      f"({rag_mems / max(soul_mems, 1):.1f}x more in RAG)")

        if soul_mems > 0 and rag_mems > 0:
            soul_efficiency = full_cr.recall_hits / soul_mems if soul_mems else 0
            rag_efficiency = rag_cr.recall_hits / rag_mems if rag_mems else 0
            lines.append(f"- **Recall per memory:** Soul {soul_efficiency:.4f} vs RAG {rag_efficiency:.4f} "
                          f"(Soul is {soul_efficiency / max(rag_efficiency, 0.0001):.1f}x more efficient)")
        lines.append("")

    # --- Recall by fact age ---
    lines.append("## Recall by Fact Age")
    lines.append("")
    lines.append("This is the critical analysis: do early-planted facts get lost more than recent ones?")
    lines.append("")

    # Table header
    header_parts = ["| Fact Age |"]
    divider_parts = ["|----------|"]
    for cond in cond_order:
        if cond in age_analysis:
            label = cond_labels[cond]
            header_parts.append(f" {label} |")
            divider_parts.append(f"{'---':->12}|")
    lines.append(" ".join(header_parts))
    lines.append(" ".join(divider_parts))

    for cat in AGE_ORDER:
        cat_label = AGE_CATEGORIES.get(cat, cat)
        row_parts = [f"| {cat_label} |"]
        for cond in cond_order:
            if cond not in age_analysis:
                continue
            cat_data = age_analysis[cond].get(cat, {"hits": 0, "total": 0, "rate": 0.0})
            rate = cat_data["rate"] * 100
            hits = cat_data["hits"]
            total = cat_data["total"]
            row_parts.append(f" {rate:5.1f}% ({hits}/{total}) |")
        lines.append(" ".join(row_parts))
    lines.append("")

    # --- Degradation analysis ---
    if rag_cr and full_cr:
        lines.append("## Degradation Analysis")
        lines.append("")
        lines.append("How recall changes from early to late facts (slope of recall rate):")
        lines.append("")

        for cond in [ConditionType.FULL_SOUL, ConditionType.RAG_ONLY]:
            if cond not in age_analysis:
                continue
            label = cond_labels[cond]
            cat_rates = []
            for cat in ["callback_early", "mid_range", "preference", "professional", "late_game"]:
                cat_data = age_analysis[cond].get(cat, {"rate": 0.0})
                cat_rates.append(cat_data["rate"] * 100)

            if len(cat_rates) >= 2:
                early_avg = sum(cat_rates[:2]) / 2
                late_avg = sum(cat_rates[-2:]) / 2
                degradation = early_avg - late_avg
                lines.append(f"- **{label}:** Early avg {early_avg:.1f}%, Late avg {late_avg:.1f}%, "
                              f"Degradation {degradation:+.1f}pp")
        lines.append("")

    # --- Memory growth ---
    lines.append("## Memory Growth Over 1000 Turns")
    lines.append("")
    for cond in [ConditionType.FULL_SOUL, ConditionType.RAG_ONLY]:
        cr = condition_results.get(cond)
        if not cr or not cr.memory_growth:
            continue
        label = cond_labels[cond]
        # Show growth at key points
        checkpoints = {}
        for turn_idx, mem_count in cr.memory_growth:
            for target in [0, 100, 250, 500, 750, 999]:
                if abs(turn_idx - target) < 15:
                    checkpoints[target] = mem_count

        growth_str = ", ".join(f"T{t}={c}" for t, c in sorted(checkpoints.items()))
        lines.append(f"- **{label}:** {growth_str}")
    lines.append("")

    # --- Missed recalls detail ---
    if full_cr:
        missed = [r for r in full_cr.recall_results if not r["hit"]]
        if missed:
            lines.append("## Missed Recalls (Full Soul)")
            lines.append("")
            for m in missed:
                lines.append(f"- **Q:** {m['query']}")
                lines.append(f"  **Expected:** {m['expected']}")
                if m.get("recalled"):
                    lines.append(f"  **Got:** {m['recalled'][0][:100]}...")
                lines.append("")

    # --- Conclusion ---
    lines.append("## Conclusion")
    lines.append("")
    if full_cr and rag_cr:
        soul_rate = full_cr.recall_precision * 100
        rag_rate = rag_cr.recall_precision * 100
        if soul_rate >= rag_rate:
            lines.append(
                f"At 1000 turns, Soul Protocol ({soul_rate:.1f}%) matches or beats "
                f"RAG ({rag_rate:.1f}%) on recall while storing "
                f"{full_cr.total_memories} memories vs RAG's {rag_cr.total_memories}. "
                f"Selective storage scales better — the signal-to-noise ratio in "
                f"Soul's memory corpus stays high while RAG drowns in noise."
            )
        else:
            lines.append(
                f"At 1000 turns, RAG ({rag_rate:.1f}%) still edges Soul ({soul_rate:.1f}%) "
                f"on raw recall, but stores {rag_cr.total_memories} memories vs Soul's "
                f"{full_cr.total_memories}. Check the recall-by-age breakdown — if RAG's "
                f"early-fact recall is degrading while Soul's stays flat, the crossover point "
                f"may be at higher turn counts. Also check recall-per-memory efficiency."
            )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    t_start = time.monotonic()

    # Generate the 1000-turn scenario
    print("Generating marathon scenario (1000 turns)...")
    scenario = generate_marathon_scenario(seed=42)
    print(f"  Scenario: {scenario.name}")
    print(f"  Turns: {scenario.turn_count}")
    print(f"  Planted facts: {len(scenario.planted_facts)}")
    print(f"  Test points: {len(scenario.test_points)}")
    print()

    # Quick sanity check
    categories = defaultdict(int)
    for tp in scenario.test_points:
        cat = _extract_category(tp.description)
        categories[cat] += 1
    print("  Test points by category:")
    for cat in AGE_ORDER:
        print(f"    {AGE_CATEGORIES.get(cat, cat)}: {categories.get(cat, 0)}")
    print()

    # Run through all 4 conditions
    runner = LongHorizonRunner()
    results = await runner.run_scenario(scenario)

    total_duration = time.monotonic() - t_start

    # --- Console output ---
    print(f"\n{'=' * 80}")
    print(f"SCALE ABLATION RESULTS — 1000-Turn Marathon")
    print(f"{'=' * 80}")

    cond_labels = {
        ConditionType.BARE_BASELINE: "Bare Baseline",
        ConditionType.PERSONALITY_ONLY: "Personality Only",
        ConditionType.RAG_ONLY: "RAG Only",
        ConditionType.FULL_SOUL: "Full Soul",
    }

    for cond in ALL_CONDITIONS:
        cr = results.condition_results.get(cond)
        if not cr:
            continue
        total_tests = cr.recall_hits + cr.recall_misses
        recall_pct = cr.recall_precision * 100
        storage_pct = cr.memory_efficiency * 100
        label = cond_labels.get(cond, cond)
        print(
            f"  {label:20s} | Recall: {cr.recall_hits:2d}/{total_tests:2d} ({recall_pct:5.1f}%) | "
            f"Memories: {cr.total_memories:5d} ({storage_pct:5.1f}% stored) | "
            f"Bond: {cr.bond_strength:5.3f}"
        )

    # Recall by age analysis
    age_analysis = _analyze_recall_by_age(results.condition_results)

    print(f"\n{'=' * 80}")
    print("RECALL BY FACT AGE")
    print(f"{'=' * 80}")

    for cat in AGE_ORDER:
        cat_label = AGE_CATEGORIES.get(cat, cat)
        parts = [f"  {cat_label:35s}"]
        for cond in [ConditionType.FULL_SOUL, ConditionType.RAG_ONLY]:
            if cond not in age_analysis:
                continue
            cat_data = age_analysis[cond].get(cat, {"hits": 0, "total": 0, "rate": 0.0})
            rate = cat_data["rate"] * 100
            hits = cat_data["hits"]
            total = cat_data["total"]
            label = cond_labels[cond]
            parts.append(f"| {label}: {rate:5.1f}% ({hits}/{total})")
        print(" ".join(parts))

    print(f"\nTotal duration: {total_duration:.1f}s")

    # --- Save results ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Raw JSON results
    raw_data = {
        "scenario": {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "turn_count": scenario.turn_count,
            "planted_facts": len(scenario.planted_facts),
            "test_points": len(scenario.test_points),
        },
        "duration_seconds": total_duration,
        "conditions": {},
        "recall_by_age": {},
    }
    for cond, cr in results.condition_results.items():
        total_tests = cr.recall_hits + cr.recall_misses
        raw_data["conditions"][cond] = {
            "recall_hits": cr.recall_hits,
            "recall_misses": cr.recall_misses,
            "recall_total": total_tests,
            "recall_precision": cr.recall_precision,
            "total_memories": cr.total_memories,
            "episodic_count": cr.episodic_count,
            "semantic_count": cr.semantic_count,
            "memory_efficiency": cr.memory_efficiency,
            "bond_strength": cr.bond_strength,
            "memory_growth": cr.memory_growth,
            "recall_results": cr.recall_results,
        }
    raw_data["recall_by_age"] = {
        cond: {
            cat: data for cat, data in cats.items()
        }
        for cond, cats in age_analysis.items()
    }

    results_path = OUTPUT_DIR / "results.json"
    results_path.write_text(json.dumps(raw_data, indent=2, default=str))
    print(f"\nResults saved to {results_path}")

    # Markdown report
    report = _generate_report(results.condition_results, age_analysis, total_duration)
    report_path = OUTPUT_DIR / "report.md"
    report_path.write_text(report)
    print(f"Report saved to {report_path}")

    # Console-friendly summary
    summary_lines = []
    summary_lines.append(f"Scale Ablation — 1000-Turn Marathon")
    summary_lines.append(f"Duration: {total_duration:.1f}s")
    summary_lines.append("")
    for cond in ALL_CONDITIONS:
        cr = results.condition_results.get(cond)
        if not cr:
            continue
        total_tests = cr.recall_hits + cr.recall_misses
        label = cond_labels.get(cond, cond)
        summary_lines.append(
            f"{label:20s}: {cr.recall_precision * 100:5.1f}% recall "
            f"({cr.recall_hits}/{total_tests}), {cr.total_memories} memories"
        )
    summary_lines.append("")

    full_cr = results.condition_results.get(ConditionType.FULL_SOUL)
    rag_cr = results.condition_results.get(ConditionType.RAG_ONLY)
    if full_cr and rag_cr:
        soul_rate = full_cr.recall_precision * 100
        rag_rate = rag_cr.recall_precision * 100
        summary_lines.append(f"Soul vs RAG: {soul_rate:.1f}% vs {rag_rate:.1f}%")
        summary_lines.append(f"Memory ratio: {full_cr.total_memories} vs {rag_cr.total_memories}")
        if full_cr.total_memories > 0:
            summary_lines.append(
                f"RAG stores {rag_cr.total_memories / max(full_cr.total_memories, 1):.1f}x more memories"
            )

    summary_path = OUTPUT_DIR / "summary.txt"
    summary_path.write_text("\n".join(summary_lines))
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
