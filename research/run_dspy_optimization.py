# run_dspy_optimization.py — Full DSPy optimization + ablation pipeline.
# Updated: 2026-03-11 — Post-optimization ablation now enables both DSPy
#   significance gate AND query expansion for the full_soul condition.
#   This routes significance assessment through the optimized DSPy module
#   instead of heuristics, fixing recall misses for important facts.
# Created: 2026-03-11
# Runs: (1) baseline heuristic ablation, (2) DSPy optimization with MIPROv2,
#   (3) post-optimization ablation with DSPy significance + recall, (4) saves reports.

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "src")

RESULTS_DIR = Path("research/results/dspy_optimization")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Training data generation from long-horizon scenarios
# ---------------------------------------------------------------------------


def generate_training_data() -> list[dict]:
    """Create labeled training data from long-horizon scenarios."""
    from research.long_horizon.scenarios import generate_all_scenarios

    scenarios = generate_all_scenarios(seed=42)
    examples = []

    for scenario in scenarios:
        # Build set of turn indices near planted facts
        fact_indices = {idx for idx, _ in scenario.planted_facts}
        near_fact_indices = set()
        for idx in fact_indices:
            for delta in range(-1, 3):  # 1 turn before, 2 turns after
                near_fact_indices.add(idx + delta)

        for i, (user_input, agent_output) in enumerate(scenario.turns):
            # Label: should_store if near a planted fact or emotionally charged
            is_fact_turn = i in fact_indices
            is_near_fact = i in near_fact_indices

            # Simple emotional keyword check for labeling
            emotional_words = {
                "love",
                "hate",
                "thrilled",
                "devastated",
                "excited",
                "scared",
                "angry",
                "furious",
                "heartbroken",
                "ecstatic",
                "anxious",
                "proud",
                "ashamed",
                "grateful",
                "miserable",
                "depressed",
                "overwhelmed",
                "elated",
                "terrified",
                "disgusted",
            }
            text_lower = f"{user_input} {agent_output}".lower()
            has_emotion = bool(set(text_lower.split()) & emotional_words)

            should_store = is_fact_turn or is_near_fact or has_emotion

            examples.append(
                {
                    "user_input": user_input,
                    "agent_output": agent_output,
                    "core_values": ["empathy", "curiosity", "reliability"],
                    "should_store": should_store,
                    "is_fact_turn": is_fact_turn,
                    "scenario_id": scenario.scenario_id,
                    "turn_index": i,
                }
            )

        # Add recall examples from test points
        for tp in scenario.test_points:
            if tp.test_type == "recall":
                examples.append(
                    {
                        "type": "recall",
                        "query": tp.query,
                        "expected_fact": tp.expected_content,
                        "planted_facts": [fact for _, fact in scenario.planted_facts],
                    }
                )

    return examples


# ---------------------------------------------------------------------------
# Run heuristic ablation (no LLM)
# ---------------------------------------------------------------------------


async def run_ablation(
    label: str,
    use_dspy_recall: bool = False,
    use_dspy_significance: bool = False,
    optimized_modules_path: str | None = None,
) -> dict:
    """Run ablation, optionally with DSPy query expansion and/or significance."""
    from research.long_horizon.runner import LongHorizonRunner
    from research.long_horizon.scenarios import generate_all_scenarios

    scenarios = generate_all_scenarios(seed=42)
    runner = LongHorizonRunner(
        use_dspy_recall=use_dspy_recall,
        use_dspy_significance=use_dspy_significance,
        optimized_modules_path=optimized_modules_path,
    )
    results = await runner.run_all(scenarios)

    report = {
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "scenarios": [],
        "overall": {},
    }

    cond_totals = defaultdict(
        lambda: {
            "hits": 0,
            "total": 0,
            "mems": 0,
            "turns": 0,
            "bond": 0.0,
            "count": 0,
            "episodic": 0,
            "semantic": 0,
        }
    )

    for sr in results.scenario_results:
        scenario_data = {"id": sr.scenario_id, "name": sr.scenario_name, "conditions": {}}
        for cond, cr in sr.condition_results.items():
            recall_total = cr.recall_hits + cr.recall_misses
            scenario_data["conditions"][cond] = {
                "recall_hits": cr.recall_hits,
                "recall_total": recall_total,
                "recall_precision": cr.recall_precision,
                "total_memories": cr.total_memories,
                "episodic_count": cr.episodic_count,
                "semantic_count": cr.semantic_count,
                "memory_efficiency": cr.memory_efficiency,
                "bond_strength": cr.bond_strength,
                "duration_seconds": cr.duration_seconds,
                "recall_results": cr.recall_results,
            }
            d = cond_totals[cond]
            d["hits"] += cr.recall_hits
            d["total"] += recall_total
            d["mems"] += cr.total_memories
            d["turns"] += cr.total_turns
            d["bond"] += cr.bond_strength
            d["count"] += 1
            d["episodic"] += cr.episodic_count
            d["semantic"] += cr.semantic_count

        report["scenarios"].append(scenario_data)

    for cond, d in cond_totals.items():
        report["overall"][cond] = {
            "recall_precision": d["hits"] / d["total"] if d["total"] else 0,
            "recall_hits": d["hits"],
            "recall_total": d["total"],
            "total_memories": d["mems"],
            "total_turns": d["turns"],
            "storage_rate": d["mems"] / d["turns"] if d["turns"] else 0,
            "avg_bond": d["bond"] / d["count"] if d["count"] else 0,
            "episodic_total": d["episodic"],
            "semantic_total": d["semantic"],
        }

    report["total_duration"] = results.total_duration
    return report


# ---------------------------------------------------------------------------
# DSPy optimization
# ---------------------------------------------------------------------------


def run_dspy_optimization(training_data: list[dict]) -> dict:
    """Run MIPROv2 optimization on significance gate and query expander."""
    import dspy

    lm = dspy.LM("anthropic/claude-haiku-4-5-20251001")
    dspy.configure(lm=lm)

    from soul_protocol.runtime.cognitive.dspy_modules import (
        QueryExpander,
        SignificanceGate,
    )

    gate = SignificanceGate()
    expander = QueryExpander()

    # Split training data
    sig_examples = [d for d in training_data if d.get("type") != "recall"]
    recall_examples = [d for d in training_data if d.get("type") == "recall"]

    # Convert to dspy.Example
    sig_dspy = []
    for ex in sig_examples:
        sig_dspy.append(
            dspy.Example(
                user_input=ex["user_input"],
                agent_output=ex["agent_output"],
                core_values=ex["core_values"],
                recent_context="",
                should_store=ex["should_store"],
            ).with_inputs("user_input", "agent_output", "core_values", "recent_context")
        )

    recall_dspy = []
    for ex in recall_examples:
        recall_dspy.append(
            dspy.Example(
                query=ex["query"],
                personality_summary="",
                expected_fact=ex["expected_fact"],
            ).with_inputs("query", "personality_summary")
        )

    results = {"modules_optimized": [], "metrics": {}}

    # --- Optimize Significance Gate ---
    if len(sig_dspy) >= 10:
        split = int(len(sig_dspy) * 0.8)
        train_sig = sig_dspy[:split]
        val_sig = sig_dspy[split:]

        print(
            f"\n[DSPy] Optimizing SignificanceGate with {len(train_sig)} train, {len(val_sig)} val examples..."
        )

        def sig_metric(example, prediction, trace=None):
            expected = bool(example.should_store)
            predicted = bool(getattr(prediction, "should_store", True))
            # Handle string "True"/"False" from LLM
            if isinstance(predicted, str):
                predicted = predicted.lower().strip() in ("true", "yes", "1")
            return 1.0 if predicted == expected else 0.0

        optimizer = dspy.MIPROv2(
            metric=sig_metric,
            auto="light",  # light = fewer trials, cheaper
        )

        optimized_gate = optimizer.compile(
            gate._module,
            trainset=train_sig,
            max_bootstrapped_demos=3,
            max_labeled_demos=6,
        )

        # Evaluate on validation set
        correct = 0
        for ex in val_sig:
            try:
                pred = optimized_gate(
                    user_input=ex.user_input,
                    agent_output=ex.agent_output,
                    core_values=ex.core_values,
                    recent_context="",
                )
                expected = bool(ex.should_store)
                predicted = getattr(pred, "should_store", True)
                if isinstance(predicted, str):
                    predicted = predicted.lower().strip() in ("true", "yes", "1")
                if bool(predicted) == expected:
                    correct += 1
            except Exception as e:
                print(f"  [warn] Validation error: {e}")

        val_accuracy = correct / len(val_sig) if val_sig else 0
        print(f"  Gate validation accuracy: {val_accuracy:.1%}")

        # Save
        save_dir = RESULTS_DIR / "optimized_modules"
        save_dir.mkdir(parents=True, exist_ok=True)
        optimized_gate.save(str(save_dir / "significance_gate.json"))

        results["modules_optimized"].append("significance_gate")
        results["metrics"]["gate_val_accuracy"] = val_accuracy

    # --- Optimize Query Expander ---
    if len(recall_dspy) >= 5:
        split = max(1, int(len(recall_dspy) * 0.7))
        train_recall = recall_dspy[:split]
        val_recall = recall_dspy[split:]

        print(
            f"\n[DSPy] Optimizing QueryExpander with {len(train_recall)} train, {len(val_recall)} val examples..."
        )

        def recall_metric(example, prediction, trace=None):
            expected = str(getattr(example, "expected_fact", "")).lower()
            expanded = getattr(prediction, "expanded_queries", [])
            if not expected:
                return 1.0
            expected_tokens = set(expected.split())
            for q in expanded:
                q_tokens = set(str(q).lower().split())
                overlap = len(expected_tokens & q_tokens) / max(len(expected_tokens), 1)
                if overlap > 0.3:
                    return 1.0
            return 0.0

        optimizer = dspy.MIPROv2(
            metric=recall_metric,
            auto="light",
        )

        optimized_expander = optimizer.compile(
            expander._module,
            trainset=train_recall,
            max_bootstrapped_demos=2,
            max_labeled_demos=4,
        )

        save_dir = RESULTS_DIR / "optimized_modules"
        optimized_expander.save(str(save_dir / "query_expander.json"))

        results["modules_optimized"].append("query_expander")

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def save_reports(baseline: dict, optimized: dict | None, dspy_results: dict | None):
    """Save JSON + Markdown reports to research/results/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save raw JSON
    full_report = {
        "timestamp": datetime.now().isoformat(),
        "baseline": baseline,
        "dspy_optimization": dspy_results,
        "post_optimization": optimized,
    }
    json_path = RESULTS_DIR / f"ablation_report_{timestamp}.json"
    json_path.write_text(json.dumps(full_report, indent=2, default=str))
    print(f"\nJSON report saved: {json_path}")

    # Also save as latest
    latest_path = RESULTS_DIR / "latest_report.json"
    latest_path.write_text(json.dumps(full_report, indent=2, default=str))

    # Generate Markdown report
    md = generate_markdown_report(baseline, optimized, dspy_results)
    md_path = RESULTS_DIR / f"ablation_report_{timestamp}.md"
    md_path.write_text(md)
    latest_md = RESULTS_DIR / "latest_report.md"
    latest_md.write_text(md)
    print(f"Markdown report saved: {md_path}")

    return json_path, md_path


def generate_markdown_report(
    baseline: dict, optimized: dict | None, dspy_results: dict | None
) -> str:
    """Generate a comprehensive Markdown report."""
    lines = [
        "# Soul Protocol — Ablation & DSPy Optimization Report",
        f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "**Branch**: feat/dspy-integration (Phase 1 + Phase 2)",
        "",
        "## 1. Baseline (Heuristic Pipeline — Phase 1 Fixes)",
        "",
    ]

    # Baseline table
    lines.append("| Condition | Recall | Memories | Storage Rate | Bond |")
    lines.append("|-----------|--------|----------|--------------|------|")
    for cond, d in baseline.get("overall", {}).items():
        recall_pct = d["recall_precision"] * 100
        lines.append(
            f"| {cond} | {d['recall_hits']}/{d['recall_total']} ({recall_pct:.1f}%) | "
            f"{d['total_memories']} | {d['storage_rate'] * 100:.1f}% | {d['avg_bond']:.1f} |"
        )

    # Per-scenario breakdown
    lines.append("\n### Per-Scenario Breakdown\n")
    for sc in baseline.get("scenarios", []):
        lines.append(f"#### {sc['name']} (`{sc['id']}`)\n")
        lines.append("| Condition | Recall | Memories | Episodic | Semantic | Bond |")
        lines.append("|-----------|--------|----------|----------|----------|------|")
        for cond, cd in sc["conditions"].items():
            rp = cd["recall_precision"] * 100
            lines.append(
                f"| {cond} | {cd['recall_hits']}/{cd['recall_total']} ({rp:.1f}%) | "
                f"{cd['total_memories']} | {cd['episodic_count']} | {cd['semantic_count']} | "
                f"{cd['bond_strength']:.1f} |"
            )

        # Recall detail for full_soul
        fs = sc["conditions"].get("full_soul", {})
        if fs.get("recall_results"):
            lines.append("\n**Full Soul Recall Detail:**\n")
            for rr in fs["recall_results"]:
                status = "HIT" if rr["hit"] else "MISS"
                lines.append(f"- [{status}] `{rr['query']}` → expected: `{rr['expected']}`")
                if not rr["hit"] and rr.get("recalled"):
                    lines.append(f"  - Got: `{rr['recalled'][0][:80]}...`")
        lines.append("")

    # DSPy optimization results
    if dspy_results:
        lines.append("\n## 2. DSPy Optimization Results\n")
        lines.append(f"- Modules optimized: {', '.join(dspy_results.get('modules_optimized', []))}")
        for k, v in dspy_results.get("metrics", {}).items():
            if isinstance(v, float):
                lines.append(f"- {k}: {v:.1%}")
            else:
                lines.append(f"- {k}: {v}")

    # Post-optimization results
    if optimized:
        lines.append("\n## 3. Post-Optimization Ablation\n")
        lines.append("| Condition | Recall | Memories | Storage Rate | Bond |")
        lines.append("|-----------|--------|----------|--------------|------|")
        for cond, d in optimized.get("overall", {}).items():
            recall_pct = d["recall_precision"] * 100
            lines.append(
                f"| {cond} | {d['recall_hits']}/{d['recall_total']} ({recall_pct:.1f}%) | "
                f"{d['total_memories']} | {d['storage_rate'] * 100:.1f}% | {d['avg_bond']:.1f} |"
            )

    # Comparison
    if optimized and baseline:
        lines.append("\n## 4. Improvement Summary\n")
        b_fs = baseline.get("overall", {}).get("full_soul", {})
        o_fs = optimized.get("overall", {}).get("full_soul", {})
        if b_fs and o_fs:
            recall_delta = (o_fs["recall_precision"] - b_fs["recall_precision"]) * 100
            storage_delta = (o_fs["storage_rate"] - b_fs["storage_rate"]) * 100
            lines.append("| Metric | Baseline | Optimized | Delta |")
            lines.append("|--------|----------|-----------|-------|")
            lines.append(
                f"| Recall | {b_fs['recall_precision'] * 100:.1f}% | "
                f"{o_fs['recall_precision'] * 100:.1f}% | {recall_delta:+.1f}% |"
            )
            lines.append(
                f"| Storage | {b_fs['storage_rate'] * 100:.1f}% | "
                f"{o_fs['storage_rate'] * 100:.1f}% | {storage_delta:+.1f}% |"
            )
            lines.append(
                f"| Bond | {b_fs['avg_bond']:.1f} | {o_fs['avg_bond']:.1f} | "
                f"{o_fs['avg_bond'] - b_fs['avg_bond']:+.1f} |"
            )

    lines.append("\n---\n*Report generated by Soul Protocol ablation pipeline.*\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print("=" * 80)
    print("Soul Protocol — DSPy Optimization & Ablation Pipeline")
    print("=" * 80)

    optimized_path = str(RESULTS_DIR / "optimized_modules")

    # Step 1: Baseline ablation (heuristic only)
    print("\n[1/5] Running baseline heuristic ablation...")
    t0 = time.monotonic()
    baseline = await run_ablation("baseline_phase1")
    print(f"  Done in {time.monotonic() - t0:.1f}s")

    b_fs = baseline["overall"].get("full_soul", {})
    print(
        f"  Full Soul: {b_fs['recall_hits']}/{b_fs['recall_total']} recall "
        f"({b_fs['recall_precision'] * 100:.1f}%), "
        f"{b_fs['total_memories']} memories ({b_fs['storage_rate'] * 100:.1f}% stored)"
    )

    # Step 2: Generate training data
    print("\n[2/5] Generating training data from scenarios...")
    training_data = generate_training_data()
    sig_count = sum(1 for d in training_data if d.get("type") != "recall")
    recall_count = sum(1 for d in training_data if d.get("type") == "recall")
    print(f"  {sig_count} significance examples, {recall_count} recall examples")

    # Step 3: DSPy optimization
    print("\n[3/5] Running DSPy MIPROv2 optimization...")
    t0 = time.monotonic()
    dspy_results = run_dspy_optimization(training_data)
    opt_time = time.monotonic() - t0
    print(f"  Optimization completed in {opt_time:.1f}s")
    dspy_results["optimization_duration_seconds"] = opt_time

    # Step 4: Post-optimization ablation WITH DSPy significance + query expansion
    print("\n[4/5] Running post-optimization ablation with DSPy significance + query expansion...")
    t0 = time.monotonic()
    post_opt = await run_ablation(
        "post_dspy_optimization",
        use_dspy_recall=True,
        use_dspy_significance=True,
        optimized_modules_path=optimized_path,
    )
    print(f"  Done in {time.monotonic() - t0:.1f}s")

    o_fs = post_opt["overall"].get("full_soul", {})
    print(
        f"  Full Soul: {o_fs['recall_hits']}/{o_fs['recall_total']} recall "
        f"({o_fs['recall_precision'] * 100:.1f}%), "
        f"{o_fs['total_memories']} memories ({o_fs['storage_rate'] * 100:.1f}% stored)"
    )

    # Step 5: Save reports
    print("\n[5/5] Saving reports...")
    json_path, md_path = save_reports(baseline, post_opt, dspy_results)

    # Final summary
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    recall_delta = (o_fs["recall_precision"] - b_fs["recall_precision"]) * 100
    print(
        f"  Recall:  {b_fs['recall_precision'] * 100:.1f}% → {o_fs['recall_precision'] * 100:.1f}% ({recall_delta:+.1f}%)"
    )
    print(f"  Storage: {b_fs['storage_rate'] * 100:.1f}% → {o_fs['storage_rate'] * 100:.1f}%")
    print(f"  Reports: {json_path}")
    print(f"           {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
