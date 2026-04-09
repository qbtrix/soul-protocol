# run.py — CLI entry point for the research simulation framework.
# Parses arguments, builds ExperimentConfig, runs simulation, and generates analysis report.
# Usage: python -m research.run [OPTIONS] or python research/run.py [OPTIONS]

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .config import ExperimentConfig, MemoryCondition, UseCase


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run Soul Protocol research simulations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=1000,
        metavar="N",
        help="Number of simulated agents (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        metavar="N",
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--conditions",
        type=str,
        default=None,
        metavar="LIST",
        help="Comma-separated conditions to run (default: all). "
        f"Options: {', '.join(c.value for c in MemoryCondition)}",
    )
    parser.add_argument(
        "--use-cases",
        type=str,
        default=None,
        metavar="LIST",
        help="Comma-separated use cases to run (default: all). "
        f"Options: {', '.join(u.value for u in UseCase)}",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="research/results",
        metavar="DIR",
        help="Output directory (default: research/results)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 10 agents, 2 conditions (none + full_soul), 1 use case (companion)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        metavar="N",
        help="Parallel batch size (default: 50)",
    )
    return parser.parse_args(argv)


def resolve_conditions(raw: str | None) -> list[MemoryCondition]:
    """Parse comma-separated condition names into enum values."""
    if raw is None:
        return list(MemoryCondition)
    lookup = {c.value: c for c in MemoryCondition}
    result = []
    for name in raw.split(","):
        name = name.strip()
        if name not in lookup:
            sys.exit(f"Unknown condition: {name!r}. Valid: {', '.join(lookup)}")
        result.append(lookup[name])
    return result


def resolve_use_cases(raw: str | None) -> list[UseCase]:
    """Parse comma-separated use-case names into enum values."""
    if raw is None:
        return list(UseCase)
    lookup = {u.value: u for u in UseCase}
    result = []
    for name in raw.split(","):
        name = name.strip()
        if name not in lookup:
            sys.exit(f"Unknown use case: {name!r}. Valid: {', '.join(lookup)}")
        result.append(lookup[name])
    return result


def build_config(args: argparse.Namespace) -> ExperimentConfig:
    """Build an ExperimentConfig from parsed CLI args."""
    if args.quick:
        return ExperimentConfig(
            num_agents=10,
            conditions=[MemoryCondition.NONE, MemoryCondition.FULL_SOUL],
            use_cases=[UseCase.PERSONAL_COMPANION],
            random_seed=args.seed,
            output_dir=args.output,
        )
    return ExperimentConfig(
        num_agents=args.agents,
        conditions=resolve_conditions(args.conditions),
        use_cases=resolve_use_cases(args.use_cases),
        random_seed=args.seed,
        output_dir=args.output,
    )


def print_plan(config: ExperimentConfig) -> None:
    """Print the experiment plan to stdout."""
    print("=" * 60)
    print("  Soul Protocol — Research Simulation")
    print("=" * 60)
    print(f"  Agents:            {config.num_agents:,}")
    print(f"  Conditions:        {', '.join(c.value for c in config.conditions)}")
    print(f"  Use cases:         {', '.join(u.value for u in config.use_cases)}")
    print(f"  Total runs:        {config.total_runs:,}")
    print(f"  Est. interactions: {config.total_interactions:,}")
    print(f"  Random seed:       {config.random_seed}")
    print(f"  Output:            {config.output_dir}")
    print("=" * 60)


def print_headline(results) -> None:
    """Print key headline numbers from simulation results."""
    rows = results.to_dataframe_rows()
    if not rows:
        return

    # Compute per-condition recall hit rates.
    from collections import defaultdict

    recall_by_condition: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        condition = row.get("condition", "")
        recall = row.get("recall_hit_rate")
        if recall is not None:
            recall_by_condition[condition].append(recall)

    means: dict[str, float] = {}
    for cond, values in recall_by_condition.items():
        if values:
            means[cond] = sum(values) / len(values)

    # Compare full_soul vs none if both present.
    full_key = MemoryCondition.FULL_SOUL.value
    none_key = MemoryCondition.NONE.value
    if full_key in means and none_key in means:
        delta = means[full_key] - means[none_key]
        pct = (delta / means[none_key] * 100) if means[none_key] else float("inf")
        print("\n  Headline: Full Soul vs No Memory:")
        print(f"    Recall hit rate delta: {delta:+.3f} ({pct:+.1f}%)")

        # Cohen's d (pooled std).
        full_vals = recall_by_condition[full_key]
        none_vals = recall_by_condition[none_key]
        if len(full_vals) > 1 and len(none_vals) > 1:
            import math

            var_f = sum((x - means[full_key]) ** 2 for x in full_vals) / (len(full_vals) - 1)
            var_n = sum((x - means[none_key]) ** 2 for x in none_vals) / (len(none_vals) - 1)
            pooled = math.sqrt((var_f + var_n) / 2)
            d = delta / pooled if pooled else 0.0
            print(f"    Cohen's d: {d:.2f}")


async def run(args: argparse.Namespace) -> None:
    """Main async entry point: simulate, analyze, report."""
    config = build_config(args)
    print_plan(config)

    start = time.monotonic()
    start_dt = datetime.now(UTC)
    print(f"\n  Started at {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Batch size: {args.batch_size}\n")

    # --- Simulation ---
    from .simulator import SimulationEngine

    engine = SimulationEngine(config)
    print("  Running simulation...")
    results = await engine.run()

    elapsed = time.monotonic() - start
    print(f"  Simulation complete in {elapsed:.1f}s ({results.duration_seconds:.1f}s engine time)")

    # --- Analysis ---
    from .analysis import ResultsAnalyzer

    rows = results.to_dataframe_rows()
    analyzer = ResultsAnalyzer(rows)

    print("\n  Analyzing results...")
    summary = analyzer.summary_table()
    print(f"\n  Summary: {len(summary)} condition x use-case groups analyzed")

    # --- Report ---
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results.save(output_path)
    analyzer.generate_report(output_path)

    total_elapsed = time.monotonic() - start
    print_headline(results)
    print(f"\n  Total time: {total_elapsed:.1f}s")
    print(f"  Report saved to: {output_path.resolve()}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> None:
    """Synchronous CLI entry point."""
    args = parse_args(argv)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
