# decide/cognitive.py — CognitiveDecider: the memory pipeline's original decision path.
# Created: feat/soul-instinct — Wraps what MemoryManager.observe() used before the
#   decision layer existed: CognitiveProcessor (LLM engine with heuristic fallback)
#   for sentiment and significance, the optional DSPy significance gate,
#   ContradictionDetector.detect for contradictions, and reconcile_fact for dedup.
#   MemoryManager uses it as the DeciderChain fallback, so a soul with no extra
#   deciders makes exactly the same decisions as before.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.memory.dedup import reconcile_fact
from soul_protocol.runtime.memory.search import tokenize

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveProcessor
    from soul_protocol.runtime.memory.contradiction import ContradictionDetector


class CognitiveDecider:
    """Decider over the soul's CognitiveProcessor / ContradictionDetector.

    Args:
        processor: The soul's CognitiveProcessor (LLM-enhanced or heuristic-only).
        contradiction_detector: The soul's ContradictionDetector.
        dspy_processor: Optional DSPy processor; when set it owns significance.
        significance_threshold: Overall-significance bar for episodic storage.
    """

    name = "cognitive"

    def __init__(
        self,
        processor: CognitiveProcessor,
        contradiction_detector: ContradictionDetector,
        dspy_processor: Any | None = None,
        significance_threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
    ) -> None:
        self._processor = processor
        self._detector = contradiction_detector
        self._dspy = dspy_processor
        self._significance_threshold = significance_threshold

    def supports(self, kind: DecisionKind) -> bool:
        return True

    async def decide(self, request: DecisionRequest) -> Decision[Any]:
        if isinstance(request, SignificanceRequest):
            return await self._significance(request)
        if isinstance(request, SentimentRequest):
            return Decision(
                kind=DecisionKind.SENTIMENT,
                value=await self._processor.detect_sentiment(request.text),
                source=self.name,
            )
        if isinstance(request, ContradictionRequest):
            results = await self._detector.detect(request.new_content, request.existing)
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
                        if r.is_contradiction and r.old_memory_id
                    ]
                ),
                source=self.name,
            )
        if isinstance(request, DedupRequest):
            action, target_id = reconcile_fact(request.new_fact, request.existing_facts)
            return Decision(
                kind=DecisionKind.DEDUP,
                value=DedupVerdict(action=cast(DedupAction, action), target_id=target_id),
                source=self.name,
            )
        raise TypeError(f"Unsupported decision request: {type(request).__name__}")

    async def _significance(self, request: SignificanceRequest) -> Decision[SignificanceVerdict]:
        interaction = request.interaction
        if self._dspy is not None:
            score = await self._dspy.assess_significance(
                interaction, request.core_values, request.recent_contents
            )
        else:
            score = await self._processor.assess_significance(
                interaction, request.core_values, request.recent_contents
            )
        token_count = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        return Decision(
            kind=DecisionKind.SIGNIFICANCE,
            value=SignificanceVerdict(
                score=score,
                overall=min(1.0, overall_significance(score, token_count=token_count)),
                significant=is_significant(
                    score, threshold=self._significance_threshold, token_count=token_count
                ),
            ),
            source=self.name,
        )
