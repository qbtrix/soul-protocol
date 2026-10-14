# decide/heuristic.py — HeuristicDecider: the existing rule-based decisions behind the Decider protocol.
# Created: feat/soul-instinct — Thin wrapper over attention.compute_significance /
#   is_significant, sentiment.detect_sentiment, ContradictionDetector.detect_heuristic
#   and dedup.reconcile_fact. Produces exactly the same verdicts as calling those
#   functions directly, so it can serve as the always-available final fallback of a
#   DeciderChain. Confidence is None because the rules are not calibrated.

from __future__ import annotations

from typing import Any, cast

from soul_protocol.runtime.decide.types import (
    ContradictionFinding,
    ContradictionRequest,
    ContradictionVerdict,
    Decision,
    DecisionKind,
    DecisionRequest,
    DedupAction,
    DedupRequest,
    DedupVerdict,
    SentimentRequest,
    SignificanceRequest,
    SignificanceVerdict,
)
from soul_protocol.runtime.memory.attention import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    compute_significance,
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.memory.contradiction import ContradictionDetector
from soul_protocol.runtime.memory.dedup import reconcile_fact
from soul_protocol.runtime.memory.search import tokenize
from soul_protocol.runtime.memory.sentiment import detect_sentiment


class HeuristicDecider:
    """Rule-based decider. Supports every DecisionKind and never abstains."""

    name = "heuristic"

    def __init__(self, significance_threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD) -> None:
        self._significance_threshold = significance_threshold
        self._contradiction_detector = ContradictionDetector(engine=None)

    def supports(self, kind: DecisionKind) -> bool:
        return True

    async def decide(self, request: DecisionRequest) -> Decision[Any]:
        if isinstance(request, SignificanceRequest):
            return self._significance(request)
        if isinstance(request, SentimentRequest):
            return Decision(
                kind=DecisionKind.SENTIMENT,
                value=detect_sentiment(request.text),
                source=self.name,
            )
        if isinstance(request, ContradictionRequest):
            return await self._contradiction(request)
        if isinstance(request, DedupRequest):
            action, target_id = reconcile_fact(request.new_fact, request.existing_facts)
            return Decision(
                kind=DecisionKind.DEDUP,
                value=DedupVerdict(action=cast(DedupAction, action), target_id=target_id),
                source=self.name,
            )
        raise TypeError(f"Unsupported decision request: {type(request).__name__}")

    def _significance(self, request: SignificanceRequest) -> Decision[SignificanceVerdict]:
        interaction = request.interaction
        score = compute_significance(interaction, request.core_values, request.recent_contents)
        # Same token count MemoryManager.observe() uses for the short-message penalty.
        token_count = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        return Decision(
            kind=DecisionKind.SIGNIFICANCE,
            value=SignificanceVerdict(
                score=score,
                overall=overall_significance(score, token_count=token_count),
                significant=is_significant(
                    score, threshold=self._significance_threshold, token_count=token_count
                ),
            ),
            source=self.name,
        )

    async def _contradiction(self, request: ContradictionRequest) -> Decision[ContradictionVerdict]:
        results = await self._contradiction_detector.detect_heuristic(
            request.new_content, request.existing
        )
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(
                findings=[
                    ContradictionFinding(
                        old_memory_id=r.old_memory_id,
                        reason=r.reason,
                        confidence=r.confidence,
                    )
                    for r in results
                    if r.is_contradiction
                ]
            ),
            source=self.name,
        )
