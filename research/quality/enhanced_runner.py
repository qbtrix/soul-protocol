# enhanced_runner.py — Runs N scenario variations × 4 conditions × M judges.
# Created: 2026-03-07
# Updated: 2026-03-07 — Added checkpoint/resume so progress survives crashes.
# Produces statistically meaningful results with error bars for the paper.

from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from soul_protocol import Soul
from soul_protocol.runtime.types import Interaction

from ..haiku_engine import HaikuCognitiveEngine
from ..litellm_engine import LiteLLMEngine
from .conditions import CONDITION_LABELS, Condition, ConditionResponse, MultiConditionResponder
from .judge import ResponseJudge
from .scenario_generator import (
    EmotionalContinuityScenario,
    HardRecallScenario,
    ResponseQualityScenario,
    generate_emotional_continuity_scenarios,
    generate_hard_recall_scenarios,
    generate_response_quality_scenarios,
)

# ---------------------------------------------------------------------------
# Judge model configs (same as multi_judge.py)
# ---------------------------------------------------------------------------

JUDGE_MODELS = {
    "haiku": {"type": "haiku"},
    "gemini-3-flash": {"type": "litellm", "model": "gemini/gemini-3-flash"},
    "deepseek-v3": {"type": "litellm", "model": "deepseek-chat"},
}

DEFAULT_JUDGES = ["haiku"]  # Use 1 judge for speed; override with --judges


def _make_engine(cfg: dict) -> HaikuCognitiveEngine | LiteLLMEngine:
    if cfg["type"] == "haiku":
        return HaikuCognitiveEngine(max_concurrent=10, max_tokens=2048)
    return LiteLLMEngine(model=cfg["model"], max_tokens=2048, max_concurrent=5)


# ---------------------------------------------------------------------------
# Test runners (one per test type, supports multi-condition)
# ---------------------------------------------------------------------------


async def _run_response_quality_variation(
    scenario: ResponseQualityScenario,
    agent_engine: HaikuCognitiveEngine,
    judge_engine: Any,
    conditions: list[Condition],
) -> dict[str, Any]:
    """Run one response quality scenario across all conditions."""
    # Birth the soul and feed conversation turns
    soul = await Soul.birth(
        name=scenario.soul_name,
        archetype=scenario.soul_archetype,
        personality="I am a warm, empathetic companion.",
        values=["empathy", "patience", "kindness"],
        engine=agent_engine,
        ocean=scenario.soul_ocean,
        communication={"warmth": "high", "verbosity": "moderate"},
    )

    for user_input, agent_output in scenario.conversation_turns:
        await soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=agent_output,
                channel="test",
            )
        )

    # Generate responses under each condition
    responder = MultiConditionResponder(soul, agent_engine)
    responses: dict[Condition, ConditionResponse] = {}
    for cond in conditions:
        responses[cond] = await responder.generate(scenario.challenge_message, cond)

    # Judge each condition against bare baseline
    judge = ResponseJudge(judge_engine)
    context = {
        "agent_name": scenario.soul_name,
        "personality_description": soul.to_system_prompt(),
        "conversation_history": [
            {"role": "user", "content": u} for u, _ in scenario.conversation_turns
        ],
        "planted_facts": [],
        "user_message": scenario.challenge_message,
    }

    scores: dict[str, dict] = {}
    baseline_response = responses[Condition.BARE_BASELINE].response

    for cond in conditions:
        if cond == Condition.BARE_BASELINE:
            continue
        result = await judge.compare_pair(
            with_soul=responses[cond].response,
            without_soul=baseline_response,
            context=context,
        )
        soul_scores = [s.score for s in result.scores if "soul:" in s.dimension]
        base_scores = [s.score for s in result.scores if "baseline:" in s.dimension]
        scores[cond.value] = {
            "score": statistics.mean(soul_scores) if soul_scores else 0,
            "baseline": statistics.mean(base_scores) if base_scores else 0,
            "winner": result.winner,
        }

    return {
        "scenario": scenario.user_name,
        "memory_count": soul.memory_count,
        "scores": scores,
    }


async def _run_hard_recall_variation(
    scenario: HardRecallScenario,
    agent_engine: HaikuCognitiveEngine,
    judge_engine: Any,
    conditions: list[Condition],
) -> dict[str, Any]:
    """Run one hard recall scenario across conditions."""
    soul = await Soul.birth(
        name=scenario.soul_name,
        archetype="attentive technical companion",
        personality="I pay close attention to details and remember what matters.",
        values=["attention", "reliability"],
        engine=agent_engine,
    )

    # Warmup + planted fact + fillers
    for user_input, agent_output in scenario.warmup_turns:
        await soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=agent_output,
                channel="test",
            )
        )

    await soul.observe(
        Interaction(
            user_input=scenario.planted_fact_input,
            agent_output=scenario.planted_fact_output,
            channel="test",
        )
    )

    for user_input, agent_output in scenario.filler_turns:
        await soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=agent_output,
                channel="test",
            )
        )

    # Check recall
    query = " ".join(scenario.planted_fact_keywords)
    recalled = await soul.recall(query=query, limit=10)
    fact_recalled = any(
        any(kw.lower() in m.content.lower() for kw in scenario.planted_fact_keywords)
        for m in recalled
    )
    fact_rank = None
    for rank, m in enumerate(recalled, 1):
        if any(kw.lower() in m.content.lower() for kw in scenario.planted_fact_keywords):
            fact_rank = rank
            break

    # Generate responses under each condition
    responder = MultiConditionResponder(soul, agent_engine)
    responses: dict[Condition, ConditionResponse] = {}
    for cond in conditions:
        responses[cond] = await responder.generate(scenario.recall_question, cond)

    # Judge
    judge = ResponseJudge(judge_engine)
    context = {
        "agent_name": scenario.soul_name,
        "personality_description": soul.to_system_prompt(),
        "conversation_history": [],
        "planted_facts": [scenario.planted_fact_input],
        "user_message": scenario.recall_question,
    }

    scores: dict[str, dict] = {}
    baseline_response = responses[Condition.BARE_BASELINE].response

    for cond in conditions:
        if cond == Condition.BARE_BASELINE:
            continue
        result = await judge.compare_pair(
            with_soul=responses[cond].response,
            without_soul=baseline_response,
            context=context,
        )
        soul_scores_list = [s.score for s in result.scores if "soul:" in s.dimension]
        base_scores_list = [s.score for s in result.scores if "baseline:" in s.dimension]
        scores[cond.value] = {
            "score": statistics.mean(soul_scores_list) if soul_scores_list else 0,
            "baseline": statistics.mean(base_scores_list) if base_scores_list else 0,
            "winner": result.winner,
        }

    return {
        "scenario": scenario.soul_name,
        "fact_recalled": fact_recalled,
        "fact_rank": fact_rank,
        "memory_count": soul.memory_count,
        "scores": scores,
    }


async def _run_emotional_continuity_variation(
    scenario: EmotionalContinuityScenario,
    agent_engine: HaikuCognitiveEngine,
    judge_engine: Any,
    conditions: list[Condition],
) -> dict[str, Any]:
    """Run one emotional continuity scenario across conditions."""
    soul = await Soul.birth(
        name=scenario.soul_name,
        archetype="emotionally aware companion",
        personality="I am deeply attuned to emotional currents.",
        values=["emotional_intelligence", "empathy"],
        engine=agent_engine,
        ocean=scenario.soul_ocean,
        communication={"warmth": "high", "verbosity": "moderate"},
    )

    for user_input, agent_output in scenario.emotional_arc:
        await soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=agent_output,
                channel="test",
            )
        )

    # Generate responses under each condition
    responder = MultiConditionResponder(soul, agent_engine)
    responses: dict[Condition, ConditionResponse] = {}
    for cond in conditions:
        responses[cond] = await responder.generate(scenario.probe_message, cond)

    # Judge
    judge = ResponseJudge(judge_engine)
    context = {
        "agent_name": scenario.soul_name,
        "personality_description": soul.to_system_prompt(),
        "conversation_history": [{"role": "user", "content": u} for u, _ in scenario.emotional_arc],
        "planted_facts": [],
        "user_message": scenario.probe_message,
    }

    scores: dict[str, dict] = {}
    baseline_response = responses[Condition.BARE_BASELINE].response

    for cond in conditions:
        if cond == Condition.BARE_BASELINE:
            continue
        result = await judge.compare_pair(
            with_soul=responses[cond].response,
            without_soul=baseline_response,
            context=context,
        )
        soul_scores_list = [s.score for s in result.scores if "soul:" in s.dimension]
        base_scores_list = [s.score for s in result.scores if "baseline:" in s.dimension]
        scores[cond.value] = {
            "score": statistics.mean(soul_scores_list) if soul_scores_list else 0,
            "baseline": statistics.mean(base_scores_list) if base_scores_list else 0,
            "winner": result.winner,
        }

    return {
        "scenario": scenario.soul_name,
        "arc": scenario.arc_description,
        "bond_strength": soul.bond.bond_strength,
        "memory_count": soul.memory_count,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_test_results(
    variations: list[dict[str, Any]],
    conditions: list[Condition],
) -> dict[str, Any]:
    """Aggregate scores across N variations for one test type."""
    agg: dict[str, dict[str, list[float]]] = {}
    for cond in conditions:
        if cond == Condition.BARE_BASELINE:
            continue
        agg[cond.value] = {"scores": [], "baselines": [], "wins": []}

    for var in variations:
        for cond_val, data in var.get("scores", {}).items():
            if cond_val in agg:
                agg[cond_val]["scores"].append(data["score"])
                agg[cond_val]["baselines"].append(data["baseline"])
                agg[cond_val]["wins"].append(1.0 if data["winner"] == "soul" else 0.0)

    summary: dict[str, Any] = {}
    for cond_val, data in agg.items():
        n = len(data["scores"])
        if n == 0:
            continue
        mean_score = statistics.mean(data["scores"])
        mean_base = statistics.mean(data["baselines"])
        std_score = statistics.stdev(data["scores"]) if n > 1 else 0.0
        ci_95 = 1.96 * std_score / math.sqrt(n) if n > 1 else 0.0
        win_rate = statistics.mean(data["wins"])
        summary[cond_val] = {
            "n": n,
            "mean": round(mean_score, 2),
            "std": round(std_score, 2),
            "ci_95": round(ci_95, 2),
            "baseline_mean": round(mean_base, 2),
            "win_rate": round(win_rate, 2),
            "delta": round(mean_score - mean_base, 2),
        }
    return summary


# ---------------------------------------------------------------------------
# Checkpoint / resume
# ---------------------------------------------------------------------------

CHECKPOINT_FILE = "research/results/enhanced/_checkpoint.json"


def _save_checkpoint(
    all_results: dict[str, dict],
    completed_keys: list[str],
    metadata: dict,
) -> None:
    """Save progress after each test-judge combo so we can resume on crash."""
    cp_path = Path(CHECKPOINT_FILE)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    cp_path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "completed_keys": completed_keys,
                "results": all_results,
            },
            indent=2,
            default=str,
        )
    )


def _load_checkpoint() -> tuple[dict[str, dict], list[str]] | None:
    """Load checkpoint if it exists. Returns (results, completed_keys) or None."""
    cp_path = Path(CHECKPOINT_FILE)
    if not cp_path.exists():
        return None
    try:
        data = json.loads(cp_path.read_text())
        return data["results"], data["completed_keys"]
    except (json.JSONDecodeError, KeyError):
        return None


def _clear_checkpoint() -> None:
    """Remove checkpoint file after successful completion."""
    cp_path = Path(CHECKPOINT_FILE)
    if cp_path.exists():
        cp_path.unlink()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run_enhanced_validation(
    n_variations: int = 10,
    tests: list[str] | None = None,
    judges: list[str] | None = None,
    output_dir: str = "research/results/enhanced",
    resume: bool = True,
) -> dict[str, Any]:
    """Run enhanced validation: N variations × 4 conditions × M judges.

    Progress is checkpointed after each test-judge combo. If the process
    crashes, re-run with --resume to pick up where it left off.
    """

    test_keys = tests or ["response", "recall", "emotional"]
    judge_keys = judges or DEFAULT_JUDGES
    conditions = list(Condition)

    # Try to resume from checkpoint
    all_results: dict[str, dict] = {}
    completed_keys: list[str] = []

    if resume:
        checkpoint = _load_checkpoint()
        if checkpoint:
            all_results, completed_keys = checkpoint
            print(f"  Resuming from checkpoint ({len(completed_keys)} test-judge combos done)")
            print(f"  Completed: {', '.join(completed_keys)}")
            print()

    print("=" * 70)
    print("  Enhanced Quality Validation")
    print("=" * 70)
    print(f"  Variations per test: {n_variations}")
    print(f"  Conditions: {', '.join(CONDITION_LABELS[c] for c in conditions)}")
    print(f"  Tests: {', '.join(test_keys)}")
    print(f"  Judges: {', '.join(judge_keys)}")
    print()

    agent_engine = HaikuCognitiveEngine(max_concurrent=10)
    start_time = time.monotonic()

    checkpoint_meta = {
        "n_variations": n_variations,
        "tests": test_keys,
        "judges": judge_keys,
        "conditions": [c.value for c in conditions],
    }

    for judge_name in judge_keys:
        judge_engine = _make_engine(JUDGE_MODELS[judge_name])
        print(f"\n  Judge: {judge_name}")
        print(f"  {'-' * 50}")

        for test_key in test_keys:
            result_key = f"{test_key}_{judge_name}"

            # Skip if already completed in a previous run
            if result_key in completed_keys:
                print(f"\n  Test: {test_key} — already done (from checkpoint)")
                continue

            print(f"\n  Test: {test_key} ({n_variations} variations)")

            variations: list[dict] = []

            if test_key == "response":
                scenarios = generate_response_quality_scenarios(n_variations)
                for i, scenario in enumerate(scenarios, 1):
                    print(
                        f"    Variation {i}/{n_variations}: {scenario.user_name}...",
                        end=" ",
                        flush=True,
                    )
                    t0 = time.monotonic()
                    try:
                        result = await _run_response_quality_variation(
                            scenario,
                            agent_engine,
                            judge_engine,
                            conditions,
                        )
                        variations.append(result)
                        print(f"done ({time.monotonic() - t0:.1f}s)")
                    except Exception as e:
                        print(f"ERROR: {e}")
                        variations.append(
                            {"scenario": scenario.user_name, "error": str(e), "scores": {}}
                        )

            elif test_key == "recall":
                scenarios = generate_hard_recall_scenarios(n_variations)
                for i, scenario in enumerate(scenarios, 1):
                    print(
                        f"    Variation {i}/{n_variations}: {scenario.soul_name}...",
                        end=" ",
                        flush=True,
                    )
                    t0 = time.monotonic()
                    try:
                        result = await _run_hard_recall_variation(
                            scenario,
                            agent_engine,
                            judge_engine,
                            conditions,
                        )
                        variations.append(result)
                        recalled = "Y" if result.get("fact_recalled") else "N"
                        print(f"done (recalled={recalled}, {time.monotonic() - t0:.1f}s)")
                    except Exception as e:
                        print(f"ERROR: {e}")
                        variations.append(
                            {"scenario": scenario.soul_name, "error": str(e), "scores": {}}
                        )

            elif test_key == "emotional":
                scenarios = generate_emotional_continuity_scenarios(n_variations)
                for i, scenario in enumerate(scenarios, 1):
                    print(
                        f"    Variation {i}/{n_variations}: {scenario.arc_description}...",
                        end=" ",
                        flush=True,
                    )
                    t0 = time.monotonic()
                    try:
                        result = await _run_emotional_continuity_variation(
                            scenario,
                            agent_engine,
                            judge_engine,
                            conditions,
                        )
                        variations.append(result)
                        print(f"done ({time.monotonic() - t0:.1f}s)")
                    except Exception as e:
                        print(f"ERROR: {e}")
                        variations.append(
                            {
                                "scenario": str(scenario.arc_description),
                                "error": str(e),
                                "scores": {},
                            }
                        )

            else:
                print(f"    Skipping unknown test: {test_key}")
                continue

            # Aggregate and checkpoint after each test-judge combo
            summary = _aggregate_test_results(variations, conditions)
            all_results[result_key] = {
                "test": test_key,
                "judge": judge_name,
                "n_variations": n_variations,
                "summary": summary,
                "variations": variations,
            }
            completed_keys.append(result_key)
            _save_checkpoint(all_results, completed_keys, checkpoint_meta)
            print(f"    [checkpoint saved — {len(completed_keys)} combos done]")

    total_elapsed = time.monotonic() - start_time

    # --- Print results table ---
    _print_results_table(all_results, test_keys, judge_keys, conditions)

    print(f"\n  Total time: {total_elapsed:.1f}s")

    # --- Save final results ---
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat(timespec="seconds").replace(":", "-").replace("+", "p")

    payload = {
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "n_variations": n_variations,
            "tests": test_keys,
            "judges": judge_keys,
            "conditions": [c.value for c in conditions],
            "total_elapsed_seconds": round(total_elapsed, 2),
        },
        "results": all_results,
    }

    json_path = out / f"enhanced_{ts}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  Results saved to {json_path}")

    # Clear checkpoint on success
    _clear_checkpoint()
    print("  Checkpoint cleared (run complete)")

    return payload


def _print_results_table(
    all_results: dict,
    test_keys: list[str],
    judge_keys: list[str],
    conditions: list[Condition],
) -> None:
    """Print a formatted results table with error bars."""
    print(f"\n\n{'=' * 80}")
    print("  Enhanced Validation Results (mean ± 95% CI)")
    print("=" * 80)

    active_conditions = [c for c in conditions if c != Condition.BARE_BASELINE]

    for judge_name in judge_keys:
        print(f"\n  Judge: {judge_name}")
        header = f"  {'Test':<22}"
        for cond in active_conditions:
            header += f"| {CONDITION_LABELS[cond]:^22}"
        print(header)
        print("  " + "-" * (22 + 24 * len(active_conditions)))

        for test_key in test_keys:
            result_key = f"{test_key}_{judge_name}"
            data = all_results.get(result_key, {})
            summary = data.get("summary", {})

            row = f"  {test_key:<22}"
            for cond in active_conditions:
                s = summary.get(cond.value, {})
                if s:
                    cell = f"{s['mean']:.1f}±{s['ci_95']:.1f} (w:{s['win_rate']:.0%})"
                else:
                    cell = "N/A"
                row += f"| {cell:^22}"
            print(row)

    print("=" * 80)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Enhanced quality validation with N variations × 4 conditions"
    )
    parser.add_argument(
        "--variations", "-n", type=int, default=10, help="Number of scenario variations per test"
    )
    parser.add_argument(
        "--tests",
        type=str,
        default=None,
        help="Comma-separated test names (response,recall,emotional)",
    )
    parser.add_argument("--judges", type=str, default=None, help="Comma-separated judge names")
    parser.add_argument("--output", type=str, default="research/results/enhanced")
    args = parser.parse_args()

    tests = args.tests.split(",") if args.tests else None
    judges = args.judges.split(",") if args.judges else None

    await run_enhanced_validation(
        n_variations=args.variations,
        tests=tests,
        judges=judges,
        output_dir=args.output,
    )


if __name__ == "__main__":
    asyncio.run(main())
