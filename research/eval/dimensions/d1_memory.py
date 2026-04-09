# d1_memory.py — Dimension 1: Memory Recall (weight: 20%)
# Created: 2026-03-12 — Thin wrapper around long_horizon runner
#
# Evaluates how well a soul recalls planted facts after many turns.
# Wraps the existing LongHorizonRunner to extract three metrics:
#   - recall_precision: fraction of test points recalled correctly
#   - storage_rate: total_memories / total_turns (lower = more selective)
#   - burial_recall: recall precision specifically on adversarial_burial scenario
#
# Score formula:
#   score = (recall_precision * 50) + ((1 - max(0, storage_rate - 0.40)) * 20) + (burial_recall * 30)

from __future__ import annotations

import logging

from research.long_horizon.runner import ConditionType, LongHorizonRunner
from research.long_horizon.scenarios import (
    generate_all_scenarios,
    generate_life_updates,
)

from ..suite import DimensionResult

logger = logging.getLogger(__name__)


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run D1 Memory Recall evaluation.

    Args:
        seed: Random seed for scenario generation.
        quick: If True, only run the life_updates scenario (fastest).

    Returns:
        DimensionResult with recall_precision, storage_rate, and burial_recall metrics.
    """
    # Build scenarios
    if quick:
        scenarios = [generate_life_updates(seed=seed)]
        logger.info("D1 quick mode: running life_updates only (%d turns)", scenarios[0].turn_count)
    else:
        scenarios = generate_all_scenarios(seed=seed)
        logger.info("D1 full mode: running %d scenarios", len(scenarios))

    # Run with full_soul and rag_only conditions
    runner = LongHorizonRunner(
        conditions=[ConditionType.FULL_SOUL, ConditionType.RAG_ONLY],
        seed=seed,
    )
    results = await runner.run_all(scenarios)

    # ---------------------------------------------------------------------------
    # Extract metrics from full_soul condition
    # ---------------------------------------------------------------------------

    total_recall_hits = 0
    total_recall_tests = 0
    total_memories = 0
    total_turns = 0
    burial_recall_precision = 0.0

    for sr in results.scenario_results:
        cr = sr.condition_results.get(ConditionType.FULL_SOUL)
        if cr is None:
            continue

        hits = cr.recall_hits
        tests = cr.recall_hits + cr.recall_misses
        total_recall_hits += hits
        total_recall_tests += tests
        total_memories += cr.total_memories
        total_turns += cr.total_turns

        # Track adversarial burial scenario specifically
        if sr.scenario_id == "adversarial_burial":
            burial_recall_precision = cr.recall_precision

    recall_precision = total_recall_hits / total_recall_tests if total_recall_tests > 0 else 0.0
    storage_rate = total_memories / total_turns if total_turns > 0 else 0.0

    # In quick mode without adversarial_burial, use overall recall as burial proxy
    if quick and burial_recall_precision == 0.0:
        burial_recall_precision = recall_precision

    # ---------------------------------------------------------------------------
    # Compute score
    # ---------------------------------------------------------------------------
    # recall_precision * 50: how much of what was planted can be recalled
    # (1 - max(0, storage_rate - 0.40)) * 20: penalize bloated memory (>40% storage)
    # burial_recall * 30: how well facts survive noise burial

    storage_penalty_factor = 1.0 - max(0.0, storage_rate - 0.40)
    storage_penalty_factor = max(0.0, min(1.0, storage_penalty_factor))  # clamp [0, 1]

    score = (
        (recall_precision * 50.0)
        + (storage_penalty_factor * 20.0)
        + (burial_recall_precision * 30.0)
    )
    score = round(max(0.0, min(100.0, score)), 2)

    # ---------------------------------------------------------------------------
    # Build result
    # ---------------------------------------------------------------------------

    metrics = {
        "recall_precision": round(recall_precision, 4),
        "storage_rate": round(storage_rate, 4),
        "burial_recall": round(burial_recall_precision, 4),
        "total_recall_hits": float(total_recall_hits),
        "total_recall_tests": float(total_recall_tests),
        "total_memories": float(total_memories),
        "total_turns": float(total_turns),
    }

    # Determine which metrics pass/fail targets
    passed: list[str] = []
    failed: list[str] = []

    if recall_precision >= 0.60:
        passed.append("recall_precision")
    else:
        failed.append("recall_precision")

    if storage_rate <= 0.50:
        passed.append("storage_rate")
    else:
        failed.append("storage_rate")

    if burial_recall_precision >= 0.50:
        passed.append("burial_recall")
    else:
        failed.append("burial_recall")

    notes = (
        f"Recall {recall_precision:.0%} ({total_recall_hits}/{total_recall_tests}), "
        f"storage rate {storage_rate:.2f}, "
        f"burial recall {burial_recall_precision:.0%}. "
        f"Score: {score}/100."
    )

    logger.info("D1 result: %s", notes)

    return DimensionResult(
        dimension_id=1,
        dimension_name="Memory Recall",
        score=score,
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
