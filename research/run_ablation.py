#!/usr/bin/env python3
"""Quick ablation runner — no API key needed."""
import asyncio
import sys
sys.path.insert(0, "src")

from research.long_horizon.scenarios import build_all_scenarios
from research.long_horizon.runner import LongHorizonRunner

async def main():
    scenarios = build_all_scenarios(seed=42)
    print(f"Built {len(scenarios)} scenarios:")
    for s in scenarios:
        print(f"  - {s.name}: {s.turn_count} turns, {len(s.test_points)} test points")

    runner = LongHorizonRunner()
    results = await runner.run_all(scenarios)

    print(f"\n{'='*80}")
    print(f"ABLATION RESULTS (Phase 1 — heuristic pipeline)")
    print(f"{'='*80}")

    for sr in results.scenario_results:
        print(f"\n--- {sr.scenario_name} ({sr.scenario_id}) ---")
        for cond, cr in sr.condition_results.items():
            recall_total = cr.recall_hits + cr.recall_misses
            recall_pct = cr.recall_precision * 100
            storage_pct = cr.memory_efficiency * 100
            print(
                f"  {cond:20s} | Recall: {cr.recall_hits}/{recall_total} ({recall_pct:5.1f}%) | "
                f"Memories: {cr.total_memories:4d} ({storage_pct:5.1f}% stored) | "
                f"Bond: {cr.bond_strength:5.1f}"
            )

    # Overall summary
    print(f"\n{'='*80}")
    print("OVERALL AVERAGES")
    print(f"{'='*80}")

    from collections import defaultdict
    cond_totals = defaultdict(lambda: {"hits": 0, "total": 0, "mems": 0, "turns": 0, "bond": 0.0, "count": 0})
    for sr in results.scenario_results:
        for cond, cr in sr.condition_results.items():
            d = cond_totals[cond]
            d["hits"] += cr.recall_hits
            d["total"] += cr.recall_hits + cr.recall_misses
            d["mems"] += cr.total_memories
            d["turns"] += cr.total_turns
            d["bond"] += cr.bond_strength
            d["count"] += 1

    for cond, d in cond_totals.items():
        recall_pct = (d["hits"] / d["total"] * 100) if d["total"] > 0 else 0
        storage_pct = (d["mems"] / d["turns"] * 100) if d["turns"] > 0 else 0
        avg_bond = d["bond"] / d["count"] if d["count"] > 0 else 0
        print(
            f"  {cond:20s} | Recall: {d['hits']}/{d['total']} ({recall_pct:5.1f}%) | "
            f"Memories: {d['mems']:4d}/{d['turns']} ({storage_pct:5.1f}% stored) | "
            f"Bond: {avg_bond:5.1f}"
        )

    print(f"\nTotal duration: {results.total_duration:.1f}s")

asyncio.run(main())
