# multi_judge.py — Run quality tests with multiple judge models for inter-rater reliability.
# Uses LiteLLM proxy to access Gemini, DeepSeek, Llama alongside our existing Haiku judge.
# Created: 2026-03-06

from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..haiku_engine import HaikuCognitiveEngine
from ..litellm_engine import LiteLLMEngine
from .test_scenarios import (
    test_emotional_continuity,
    test_hard_recall,
    test_personality_consistency,
    test_response_quality,
)

# ---------------------------------------------------------------------------
# Judge model configs — each gets its own engine
# ---------------------------------------------------------------------------

JUDGE_MODELS = {
    "haiku": {"type": "haiku"},
    "gemini-3-flash": {"type": "litellm", "model": "gemini/gemini-3-flash"},
    "gemini-2.5-flash-lite": {"type": "litellm", "model": "gemini/gemini-2.5-flash-lite"},
    "deepseek-v3": {"type": "litellm", "model": "deepseek-chat"},
    "llama-3.3-70b": {"type": "litellm", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
}

TEST_REGISTRY = {
    "response": ("Response Quality", test_response_quality),
    "personality": ("Personality Consistency", test_personality_consistency),
    "recall": ("Hard Recall", test_hard_recall),
    "emotional": ("Emotional Continuity", test_emotional_continuity),
}


def _make_engine(cfg: dict) -> HaikuCognitiveEngine | LiteLLMEngine:
    if cfg["type"] == "haiku":
        return HaikuCognitiveEngine(max_concurrent=10, max_tokens=2048)
    return LiteLLMEngine(model=cfg["model"], max_tokens=2048, max_concurrent=5)


def _extract_scores(result: dict) -> tuple[float | None, float | None]:
    soul = result.get("soul_score") or result.get("soul_avg")
    baseline = result.get("baseline_score") or result.get("baseline_avg")
    return soul, baseline


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run_multi_judge(
    tests: list[str] | None = None,
    judges: list[str] | None = None,
    output_dir: str = "research/results/multi_judge",
) -> dict[str, Any]:
    """Run quality tests across multiple judge models.

    Each test is run once (shared agent engine), then judged by each model
    separately. This gives us inter-rater reliability data.
    """
    test_keys = tests or list(TEST_REGISTRY.keys())
    judge_keys = judges or list(JUDGE_MODELS.keys())

    print("=" * 60)
    print("  Multi-Judge Quality Validation")
    print("=" * 60)
    print(f"  Tests: {', '.join(test_keys)}")
    print(f"  Judges: {', '.join(judge_keys)}")
    print()

    # Single agent engine shared across all tests
    agent_engine = HaikuCognitiveEngine(max_concurrent=10)

    # Create judge engines
    judge_engines: dict[str, Any] = {}
    for jk in judge_keys:
        judge_engines[jk] = _make_engine(JUDGE_MODELS[jk])

    all_results: dict[str, dict[str, dict]] = {}  # test -> judge -> result
    start_time = time.monotonic()

    for test_key in test_keys:
        display_name, test_fn = TEST_REGISTRY[test_key]
        print(f"\n{'=' * 50}")
        print(f"  Test: {display_name}")
        print(f"{'=' * 50}")

        all_results[test_key] = {}

        # Run each judge sequentially (they each run the full test independently)
        for jk in judge_keys:
            print(f"\n  Judge: {jk}")
            je = judge_engines[jk]
            t0 = time.monotonic()

            try:
                result = await test_fn(agent_engine, je)
                elapsed = time.monotonic() - t0
                result["judge_model"] = jk
                result["judge_elapsed_seconds"] = round(elapsed, 2)
                all_results[test_key][jk] = result

                soul, baseline = _extract_scores(result)
                winner = result.get("winner", "?")
                print(f"    Soul: {soul}, Baseline: {baseline}, Winner: {winner} ({elapsed:.1f}s)")

            except Exception as e:
                elapsed = time.monotonic() - t0
                print(f"    ERROR: {e} ({elapsed:.1f}s)")
                all_results[test_key][jk] = {
                    "status": "error",
                    "error": str(e),
                    "judge_model": jk,
                    "judge_elapsed_seconds": round(elapsed, 2),
                }

    total_elapsed = time.monotonic() - start_time

    # --- Print scorecard ---
    print(f"\n\n{'=' * 70}")
    print("  Multi-Judge Scorecard")
    print("=" * 70)

    # Header
    header = f"  {'Test':<26}"
    for jk in judge_keys:
        header += f"| {jk[:14]:^16}"
    print(header)
    print("  " + "-" * (26 + 18 * len(judge_keys)))

    # Per-test rows
    judge_soul_totals: dict[str, list[float]] = {jk: [] for jk in judge_keys}
    judge_baseline_totals: dict[str, list[float]] = {jk: [] for jk in judge_keys}

    for test_key in test_keys:
        display_name = TEST_REGISTRY[test_key][0]
        row = f"  {display_name:<26}"
        for jk in judge_keys:
            result = all_results.get(test_key, {}).get(jk, {})
            soul, baseline = _extract_scores(result)
            if soul is not None:
                judge_soul_totals[jk].append(soul)
            if baseline is not None:
                judge_baseline_totals[jk].append(baseline)
            cell = f"{soul or 0:.1f}/{baseline or 0:.1f}" if soul is not None else "ERR"
            row += f"| {cell:^16}"
        print(row)

    # Overall row
    print("  " + "-" * (26 + 18 * len(judge_keys)))
    row = f"  {'Overall':<26}"
    for jk in judge_keys:
        s_avg = statistics.mean(judge_soul_totals[jk]) if judge_soul_totals[jk] else 0
        b_avg = statistics.mean(judge_baseline_totals[jk]) if judge_baseline_totals[jk] else 0
        row += f"| {s_avg:.1f}/{b_avg:.1f}".ljust(17)
    print(row)

    # --- Inter-rater agreement ---
    print("\n  Inter-Judge Agreement (per test):")
    for test_key in test_keys:
        display_name = TEST_REGISTRY[test_key][0]
        soul_scores = []
        for jk in judge_keys:
            result = all_results.get(test_key, {}).get(jk, {})
            soul, _ = _extract_scores(result)
            if soul is not None:
                soul_scores.append(soul)
        if len(soul_scores) >= 2:
            mean = statistics.mean(soul_scores)
            stdev = statistics.stdev(soul_scores)
            spread = max(soul_scores) - min(soul_scores)
            print(f"    {display_name:<26} mean={mean:.1f} std={stdev:.1f} spread={spread:.1f}")

    print(f"\n  Total time: {total_elapsed:.1f}s")
    print("=" * 70)

    # --- Save results ---
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat(timespec="seconds").replace(":", "-").replace("+", "p")

    # Serialize judge results (strip non-serializable objects)
    def _clean(obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return str(obj)
        return obj

    payload = {
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "tests": test_keys,
            "judges": judge_keys,
            "total_elapsed_seconds": round(total_elapsed, 2),
        },
        "results": all_results,
    }

    json_path = out / f"multi_judge_{ts}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=_clean))
    print(f"\n  Results saved to {json_path}")

    return payload


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Multi-judge quality validation")
    parser.add_argument("--tests", type=str, default=None, help="Comma-separated test names")
    parser.add_argument("--judges", type=str, default=None, help="Comma-separated judge names")
    parser.add_argument("--output", type=str, default="research/results/multi_judge")
    args = parser.parse_args()

    tests = args.tests.split(",") if args.tests else None
    judges = args.judges.split(",") if args.judges else None

    await run_multi_judge(tests=tests, judges=judges, output_dir=args.output)


if __name__ == "__main__":
    asyncio.run(main())
