# research/quality/run_quality.py
# Created: CLI runner for Soul Protocol quality validation tests.
# Runs fixed scenarios (response quality, personality consistency, hard recall,
# emotional continuity) using paired HaikuCognitiveEngine instances for agent
# and judge roles. Outputs a scorecard to stdout and saves JSON + markdown
# results to the output directory.
"""
Quality validation runner for Soul Protocol.

Usage:
    python -m research.quality.run_quality
    python -m research.quality.run_quality --tests recall,emotional
    python -m research.quality.run_quality --output results/ --max-concurrent 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..haiku_engine import HaikuCognitiveEngine
from .test_scenarios import (
    test_emotional_continuity,
    test_hard_recall,
    test_personality_consistency,
    test_response_quality,
)

# ---------------------------------------------------------------------------
# Test registry — maps CLI short-names to (display name, async callable)
# ---------------------------------------------------------------------------

TEST_REGISTRY: dict[str, tuple[str, Any]] = {
    "response": ("Response Quality", test_response_quality),
    "personality": ("Personality Consistency", test_personality_consistency),
    "recall": ("Hard Recall", test_hard_recall),
    "emotional": ("Emotional Continuity", test_emotional_continuity),
}

ALL_TEST_NAMES = list(TEST_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Soul Protocol quality validation runner",
    )
    parser.add_argument(
        "--tests",
        type=str,
        default=",".join(ALL_TEST_NAMES),
        help=(
            "Comma-separated list of tests to run. "
            f"Options: {', '.join(ALL_TEST_NAMES)} (default: all)"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="research/results/quality",
        help="Output directory for results (default: research/results/quality)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Max concurrent API calls per engine (default: 10)",
    )
    return parser.parse_args(argv)


def _resolve_tests(raw: str) -> list[str]:
    """Validate and return the ordered list of test keys."""
    requested = [t.strip() for t in raw.split(",") if t.strip()]
    unknown = [t for t in requested if t not in TEST_REGISTRY]
    if unknown:
        sys.exit(
            f"Unknown test(s): {', '.join(unknown)}. Valid options: {', '.join(ALL_TEST_NAMES)}"
        )
    return requested


def _extract_scores(result: dict) -> tuple[float | None, float | None]:
    """Pull soul_score and baseline_score from a test result dict."""
    soul = result.get("soul_score") or result.get("soul_avg")
    baseline = result.get("baseline_score") or result.get("baseline_avg")
    return soul, baseline


def _winner(soul: float | None, baseline: float | None) -> str:
    if soul is None:
        return "N/A"
    if baseline is None:
        return "SOUL"
    if soul > baseline:
        return "SOUL"
    if baseline > soul:
        return "BASE"
    return "TIE"


def _fmt(val: float | None, width: int = 5) -> str:
    if val is None:
        return "N/A".center(width)
    return f"{val:.1f}".center(width)


# ---------------------------------------------------------------------------
# Scorecard rendering
# ---------------------------------------------------------------------------

_LINE = "=" * 60
_DASH = "-" * 60


def _print_scorecard(
    results: dict[str, dict],
    test_keys: list[str],
    agent_usage: dict,
    judge_usage: dict,
) -> str:
    """Print and return the final scorecard as a string."""
    lines: list[str] = []

    def p(text: str = "") -> None:
        lines.append(text)
        print(text)

    p(_LINE)
    p("  Soul Protocol Quality Validation -- Scorecard")
    p(_LINE)
    p(f"  {'Test':<26}| {'Winner':<9}| {'Soul Score':<12}| Baseline")
    p(_DASH)

    soul_scores: list[float] = []
    baseline_scores: list[float] = []

    for key in test_keys:
        display_name = TEST_REGISTRY[key][0]
        result = results.get(key, {})
        soul, baseline = _extract_scores(result)
        win = _winner(soul, baseline)

        if soul is not None:
            soul_scores.append(soul)
        if baseline is not None:
            baseline_scores.append(baseline)

        p(f"  {display_name:<26}| {win:<9}| {_fmt(soul, 10):<12}| {_fmt(baseline)}")

    p(_DASH)

    overall_soul = sum(soul_scores) / len(soul_scores) if soul_scores else None
    overall_base = sum(baseline_scores) / len(baseline_scores) if baseline_scores else None
    overall_win = _winner(overall_soul, overall_base)

    p(f"  {'Overall':<26}| {overall_win:<9}| {_fmt(overall_soul, 10):<12}| {_fmt(overall_base)}")
    p()

    agent_calls = agent_usage.get("calls", 0)
    agent_cost = agent_usage.get("estimated_cost_usd", 0.0)
    judge_calls = judge_usage.get("calls", 0)
    judge_cost = judge_usage.get("estimated_cost_usd", 0.0)
    total_cost = agent_cost + judge_cost

    p("  API Usage:")
    p(f"    Agent engine: {agent_calls} calls, ${agent_cost:.4f}")
    p(f"    Judge engine: {judge_calls} calls, ${judge_cost:.4f}")
    p(f"    Total: ${total_cost:.4f}")
    p(_LINE)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------


def _save_results(
    output_dir: Path,
    results: dict[str, dict],
    scorecard_text: str,
    metadata: dict,
) -> None:
    """Write JSON results and markdown scorecard to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = metadata.get("timestamp", datetime.now(UTC).isoformat())
    stem = timestamp.replace(":", "-").replace("+", "p")

    # JSON — full results
    json_path = output_dir / f"quality_{stem}.json"
    payload = {
        "metadata": metadata,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nResults saved to {json_path}")

    # Markdown — scorecard
    md_path = output_dir / f"quality_{stem}.md"
    md_content = (
        f"# Quality Validation Results\n\n**Date:** {timestamp}\n\n```\n{scorecard_text}\n```\n"
    )
    md_path.write_text(md_content)
    print(f"Scorecard saved to {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    test_keys = _resolve_tests(args.tests)
    output_dir = Path(args.output)

    print(f"Running quality tests: {', '.join(test_keys)}")
    print(f"Max concurrent calls: {args.max_concurrent}")
    print(f"Output directory: {output_dir}\n")

    # Two separate engines so we can track costs independently
    agent_engine = HaikuCognitiveEngine(max_concurrent=args.max_concurrent)
    # Judge needs higher max_tokens — pairwise comparison JSON is ~800 tokens
    judge_engine = HaikuCognitiveEngine(max_concurrent=args.max_concurrent, max_tokens=2048)

    results: dict[str, dict] = {}
    start_time = time.monotonic()

    for key in test_keys:
        display_name, test_fn = TEST_REGISTRY[key]
        print(f"\n{'=' * 40}")
        print(f"  Running: {display_name}")
        print(f"{'=' * 40}\n")

        test_start = time.monotonic()
        result = await test_fn(agent_engine, judge_engine)
        elapsed = time.monotonic() - test_start

        result["elapsed_seconds"] = round(elapsed, 2)
        results[key] = result

        # Per-test summary
        soul, baseline = _extract_scores(result)
        win = _winner(soul, baseline)
        print(f"\n  Result: {display_name}")
        print(f"    Soul score:     {_fmt(soul)}")
        print(f"    Baseline score: {_fmt(baseline)}")
        print(f"    Winner:         {win}")
        print(f"    Time:           {elapsed:.1f}s")

    total_elapsed = time.monotonic() - start_time

    # Gather usage from both engines
    agent_usage = {
        "calls": agent_engine.usage.calls,
        "estimated_cost_usd": agent_engine.usage.estimated_cost_usd,
        "input_tokens": agent_engine.usage.input_tokens,
        "output_tokens": agent_engine.usage.output_tokens,
        "summary": agent_engine.usage.summary(),
    }
    judge_usage = {
        "calls": judge_engine.usage.calls,
        "estimated_cost_usd": judge_engine.usage.estimated_cost_usd,
        "input_tokens": judge_engine.usage.input_tokens,
        "output_tokens": judge_engine.usage.output_tokens,
        "summary": judge_engine.usage.summary(),
    }

    print(f"\n\nAll tests complete in {total_elapsed:.1f}s\n")

    scorecard_text = _print_scorecard(results, test_keys, agent_usage, judge_usage)

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    metadata = {
        "timestamp": timestamp,
        "tests_run": test_keys,
        "max_concurrent": args.max_concurrent,
        "total_elapsed_seconds": round(total_elapsed, 2),
        "agent_usage": agent_usage,
        "judge_usage": judge_usage,
    }

    _save_results(output_dir, results, scorecard_text, metadata)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
