# decide/review.py — Re-check uncertain instinct decisions with a stronger reviewer.
# Created: feat/soul-instinct — The slow "System 2" pass behind Soul.review_instincts()
#   and dream(). For every memory whose decision was made while a model decider was
#   unsure, the reviewer (usually an LLM via EngineDecider) answers the same question:
#     - contradiction: the old memory is superseded if the reviewer says it is
#       contradicted, and restored if it was superseded but the reviewer disagrees.
#     - significance: the verdict is recorded (memories are never deleted here).
#   Each review is also a lesson: whether the unsure model was right is recorded in
#   the soul's InstinctCalibration, so that decider's future confidence is adjusted.
# Updated: feat/soul-instinct (#322 review) — Review no longer overwrites the
#   memory's own confidence with the reviewer's. Once reviewed, the memory gets
#   back the original_confidence saved in its marker before instinct lowered it;
#   the reviewer's confidence stays in marker["reviewed"].

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from soul_protocol.runtime.decide.types import (
    ContradictionRequest,
    DecisionKind,
    SignificanceRequest,
)
from soul_protocol.runtime.types import InstinctCalibration, Interaction, MemoryEntry

if TYPE_CHECKING:
    from soul_protocol.runtime.decide.protocol import Decider
    from soul_protocol.runtime.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_LIMIT: int = 50


class InstinctReviewReport(BaseModel):
    """Outcome of one review pass."""

    reviewer: str | None = None
    reviewed: int = 0
    agreed: int = 0
    corrected: int = 0
    restored: int = 0
    superseded: int = 0
    skipped: int = 0
    errors: int = 0
    note: str = ""
    corrections: list[dict] = Field(default_factory=list)


async def review_instincts(
    memory: MemoryManager,
    reviewer: Decider | None,
    calibration: InstinctCalibration,
    *,
    core_values: list[str] | None = None,
    include_confident: bool = False,
    limit: int = DEFAULT_REVIEW_LIMIT,
) -> InstinctReviewReport:
    """Review instinct-marked memories and apply the reviewer's verdicts.

    Args:
        memory: The soul's MemoryManager.
        reviewer: Decider to trust as ground truth. None → nothing reviewed.
        calibration: The soul's calibration; updated in place.
        core_values: Core values passed to significance reviews.
        include_confident: Also review confidently-made model decisions (gives
            calibration data for the high-confidence bands).
        limit: Maximum memories reviewed in this pass.
    """
    from soul_protocol.runtime.memory.manager import INSTINCT_METADATA_KEY

    if reviewer is None:
        return InstinctReviewReport(note="no reviewer available (attach an LLM engine)")

    report = InstinctReviewReport(reviewer=reviewer.name)
    candidates = [
        e
        for e in memory.instinct_entries(uncertain_only=not include_confident)
        if not e.metadata[INSTINCT_METADATA_KEY].get("reviewed")
    ]
    for entry in candidates[:limit]:
        marker = entry.metadata[INSTINCT_METADATA_KEY]
        kind = marker.get("kind")
        if kind not in (DecisionKind.SIGNIFICANCE, DecisionKind.CONTRADICTION) or not (
            reviewer.supports(DecisionKind(kind))
        ):
            report.skipped += 1
            continue
        try:
            if kind == DecisionKind.CONTRADICTION:
                truth, confidence = await _review_contradiction(reviewer, entry, marker)
            else:
                truth, confidence = await _review_significance(reviewer, entry, core_values or [])
        except Exception:
            logger.warning("Instinct review failed for memory %s", entry.id, exc_info=True)
            report.errors += 1
            continue
        if truth is None:
            report.skipped += 1
            continue

        if kind == DecisionKind.CONTRADICTION:
            _apply_contradiction_verdict(entry, marker, truth, report)

        if marker.get("source") and marker.get("confidence") is not None:
            calibration.record(
                marker["source"],
                kind,
                marker["confidence"],
                correct=bool(marker.get("model_verdict")) == truth,
            )
        report.reviewed += 1
        if bool(marker.get("applied")) == truth:
            report.agreed += 1
        else:
            report.corrected += 1
            report.corrections.append(
                {"memory_id": entry.id, "kind": kind, "was": marker.get("applied"), "now": truth}
            )
        entry.metadata = {
            **entry.metadata,
            INSTINCT_METADATA_KEY: {
                **marker,
                "uncertain": False,
                "applied": truth,
                "reviewed": {"by": reviewer.name, "verdict": truth, "confidence": confidence},
            },
        }
        # The uncertainty is resolved: restore the confidence the memory had
        # before instinct lowered it. The reviewer's own confidence is kept in
        # marker["reviewed"]; it says how sure the reviewer is, not the memory.
        original = marker.get("original_confidence")
        if original is not None:
            entry.confidence = original
    return report


async def _review_contradiction(
    reviewer: Decider, entry: MemoryEntry, marker: dict
) -> tuple[bool | None, float | None]:
    # Present the old memory as live so candidate selection doesn't skip it.
    probe = entry.model_copy(update={"superseded": False, "superseded_by": None})
    decision = await reviewer.decide(
        ContradictionRequest(new_content=marker.get("new_content", ""), existing=[probe])
    )
    if decision is None:
        return None, None
    flagged = any(f.old_memory_id == entry.id for f in decision.value.findings)
    return flagged, decision.confidence


async def _review_significance(
    reviewer: Decider, entry: MemoryEntry, core_values: list[str]
) -> tuple[bool | None, float | None]:
    decision = await reviewer.decide(
        SignificanceRequest(
            interaction=Interaction.from_pair(entry.content, ""),
            core_values=core_values,
        )
    )
    if decision is None:
        return None, None
    return decision.value.significant, decision.confidence


def _apply_contradiction_verdict(
    entry: MemoryEntry, marker: dict, contradicted: bool, report: InstinctReviewReport
) -> None:
    new_id = marker.get("new_id")
    is_superseded = entry.superseded or entry.superseded_by is not None
    if contradicted and not is_superseded:
        entry.superseded = True
        entry.superseded_by = new_id
        report.superseded += 1
    elif not contradicted and is_superseded and entry.superseded_by == new_id:
        entry.superseded = False
        entry.superseded_by = None
        report.restored += 1
