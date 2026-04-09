# suite.py — Soul Health Score evaluation suite runner.
# Created: 2026-03-12 — 7-dimension eval framework (EVAL-FRAMEWORK.md)
#
# Runs all (or selected) SHS dimensions, computes the weighted composite
# score, and returns a structured SoulHealthReport for analysis or JSON export.
#
# CLI usage:
#   python -m research.eval.suite [--quick] [--dimensions 1 2 4] [--seed 42] [--output path.json]

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SHS dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DIMENSION_WEIGHTS: dict[int, float] = {
    1: 0.20,  # D1 — Memory Recall
    2: 0.20,  # D2 — Emotional Intelligence
    3: 0.15,  # D3 — Personality Expression
    4: 0.15,  # D4 — Bond / Relationship
    5: 0.15,  # D5 — Self-Model
    6: 0.10,  # D6 — Identity Continuity
    7: 0.05,  # D7 — Portability
}

DIMENSION_NAMES: dict[int, str] = {
    1: "Memory Recall",
    2: "Emotional Intelligence",
    3: "Personality Expression",
    4: "Bond / Relationship",
    5: "Self-Model",
    6: "Identity Continuity",
    7: "Portability",
}

_SOUL_PROTOCOL_VERSION = "0.2.3"


# ---------------------------------------------------------------------------
# Result data models
# ---------------------------------------------------------------------------


@dataclass
class DimensionResult:
    """Result from evaluating a single SHS dimension."""

    dimension_id: int  # 1-7
    dimension_name: str
    score: float  # 0-100
    metrics: dict[str, Any] = field(default_factory=dict)
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SoulHealthReport:
    """Complete Soul Health Score report across all dimensions."""

    soul_health_score: float  # 0-100 composite
    dimension_results: list[DimensionResult] = field(default_factory=list)
    run_id: str = ""
    seed: int = 42
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str = _SOUL_PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


def compute_shs(results: list[DimensionResult]) -> float:
    """Compute composite Soul Health Score from dimension results."""
    total = 0.0
    weight_sum = 0.0
    for r in results:
        w = DIMENSION_WEIGHTS.get(r.dimension_id, 0.0)
        total += r.score * w
        weight_sum += w
    return round(total / weight_sum, 2) if weight_sum > 0 else 0.0


# ---------------------------------------------------------------------------
# Dimension runner registry
# ---------------------------------------------------------------------------

# Type alias for evaluate(seed, quick) -> DimensionResult
EvalFunc = Callable[..., Awaitable[DimensionResult]]

_DIMENSION_RUNNERS: dict[int, EvalFunc] = {}


def _register_dimensions() -> None:
    """Import and register all implemented dimension evaluators."""
    modules: list[tuple[int, str]] = [
        (1, "research.eval.dimensions.d1_memory"),
        (2, "research.eval.dimensions.d2_emotion"),
        (3, "research.eval.dimensions.d3_personality"),
        (4, "research.eval.dimensions.d4_bond"),
        (5, "research.eval.dimensions.d5_self_model"),
        (6, "research.eval.dimensions.d6_continuity"),
        (7, "research.eval.dimensions.d7_portability"),
    ]
    for dim_id, module_path in modules:
        try:
            import importlib

            mod = importlib.import_module(module_path)
            _DIMENSION_RUNNERS[dim_id] = mod.evaluate
        except (ImportError, AttributeError):
            logger.debug("D%d not available: %s", dim_id, module_path)


def _placeholder_result(dim_id: int) -> DimensionResult:
    """Create a placeholder result for an unimplemented dimension."""
    return DimensionResult(
        dimension_id=dim_id,
        dimension_name=DIMENSION_NAMES.get(dim_id, f"Unknown D{dim_id}"),
        score=0.0,
        metrics={},
        passed=[],
        failed=[],
        notes="Not yet implemented",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_eval_suite(
    seed: int = 42,
    dimensions: list[int] | None = None,
    quick: bool = False,
) -> SoulHealthReport:
    """Run the Soul Health Score evaluation suite.

    Args:
        seed: Random seed for reproducibility.
        dimensions: Which dimensions to run (1-7). None means all 7.
        quick: If True, use reduced turn counts for faster iteration.

    Returns:
        SoulHealthReport with composite score and per-dimension results.
    """
    _register_dimensions()

    dims_to_run = dimensions if dimensions is not None else list(range(1, 8))
    run_id = str(uuid.uuid4())

    logger.info(
        "Starting SHS eval: run_id=%s seed=%d dims=%s quick=%s",
        run_id,
        seed,
        dims_to_run,
        quick,
    )

    results: list[DimensionResult] = []

    for dim_id in sorted(dims_to_run):
        if dim_id not in range(1, 8):
            logger.warning("Skipping invalid dimension id: %d", dim_id)
            continue

        runner = _DIMENSION_RUNNERS.get(dim_id)
        if runner is not None:
            logger.info("Running D%d: %s", dim_id, DIMENSION_NAMES[dim_id])
            try:
                result = await runner(seed=seed, quick=quick)
                results.append(result)
            except Exception:
                logger.exception("D%d evaluation failed", dim_id)
                results.append(_placeholder_result(dim_id))
        else:
            logger.info(
                "D%d: %s — not implemented, placeholder",
                dim_id,
                DIMENSION_NAMES[dim_id],
            )
            results.append(_placeholder_result(dim_id))

    composite = compute_shs(results)

    report = SoulHealthReport(
        soul_health_score=composite,
        dimension_results=results,
        run_id=run_id,
        seed=seed,
        version=_SOUL_PROTOCOL_VERSION,
    )

    logger.info("SHS eval complete: score=%.2f/100", composite)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.eval.suite",
        description="Run the Soul Health Score evaluation suite.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        default=None,
        help="Which dimensions to evaluate (1-7). Omit for all.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Reduced turn counts for faster iteration.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write JSON report to file (default: stdout).",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Print colorful terminal dashboard instead of JSON.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = asyncio.run(
        run_eval_suite(
            seed=args.seed,
            dimensions=args.dimensions,
            quick=args.quick,
        )
    )

    if args.dashboard:
        from research.eval.report import print_dashboard

        print_dashboard(report)
    elif args.output:
        with open(args.output, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
            f.write("\n")
        logger.info("Report written to %s", args.output)
    else:
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
