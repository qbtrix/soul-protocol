# decide/chain.py — DeciderChain: confidence-gated fallback across decision backends.
# Created: feat/soul-instinct — Tries each decider in order and accepts the first
#   answer whose confidence meets ``min_confidence``. Deciders that don't support
#   the request kind, abstain, raise, or are unsure are skipped. The final fallback
#   (HeuristicDecider by default) always answers, so the memory pipeline never
#   breaks because a model backend is offline or uncertain. Every consulted
#   decider is recorded on Decision.attempts, and an optional per-soul
#   InstinctCalibration adjusts raw confidences using past review outcomes.

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from soul_protocol.runtime.decide.heuristic import HeuristicDecider
from soul_protocol.runtime.decide.protocol import Decider
from soul_protocol.runtime.decide.types import (
    ContradictionRequest,
    ContradictionVerdict,
    Decision,
    DecisionAttempt,
    DecisionKind,
    DecisionRequest,
    DedupRequest,
    DedupVerdict,
    SentimentRequest,
    SignificanceRequest,
    SignificanceVerdict,
)
from soul_protocol.runtime.types import (
    InstinctCalibration,
    Interaction,
    MemoryEntry,
    SomaticMarker,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE: float = 0.7


class DeciderChain:
    """Ask deciders in order; fall back to rules when nobody is confident.

    Usage::

        chain = DeciderChain([my_local_decider, jev_decider])
        decision = await chain.contradictions("User is vegetarian", memories)
        decision.value.findings   # typed
        decision.source           # which backend answered
        decision.attempts         # what every consulted decider said

    Args:
        deciders: Backends to try, most preferred first.
        min_confidence: Minimum (calibrated) confidence for a non-fallback
            answer to be accepted. Answers with ``confidence=None`` are never
            accepted from a non-fallback decider.
        fallback: Final decider, always accepted. Defaults to HeuristicDecider.
        calibration: Optional learned calibration; when given, each decider's
            raw confidence is replaced by its calibrated value before gating.
    """

    name = "chain"

    def __init__(
        self,
        deciders: Sequence[Decider] = (),
        *,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        fallback: Decider | None = None,
        calibration: InstinctCalibration | None = None,
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be in [0, 1], got {min_confidence}")
        self._deciders = list(deciders)
        self._fallback: Decider = fallback if fallback is not None else HeuristicDecider()
        self._calibration = calibration
        self.min_confidence = min_confidence

    @property
    def deciders(self) -> list[Decider]:
        """The non-fallback deciders, in the order they are tried."""
        return list(self._deciders)

    @property
    def fallback(self) -> Decider:
        return self._fallback

    def supports(self, kind: DecisionKind) -> bool:
        return self._fallback.supports(kind) or any(d.supports(kind) for d in self._deciders)

    def _effective(self, source: str, kind: DecisionKind, confidence: float) -> float:
        if self._calibration is None:
            return confidence
        return self._calibration.calibrate(source, kind, confidence)

    async def decide(self, request: DecisionRequest) -> Decision[Any]:
        attempts: list[DecisionAttempt] = []
        for decider in self._deciders:
            if not decider.supports(request.kind):
                continue
            try:
                decision = await decider.decide(request)
            except Exception:
                logger.warning(
                    "Decider %r failed on %s, trying next",
                    decider.name,
                    request.kind,
                    exc_info=True,
                )
                attempts.append(DecisionAttempt(source=decider.name, outcome="error"))
                continue
            if decision is None:
                attempts.append(DecisionAttempt(source=decider.name, outcome="abstained"))
                continue

            effective = (
                None
                if decision.confidence is None
                else self._effective(decider.name, request.kind, decision.confidence)
            )
            accepted = effective is not None and effective >= self.min_confidence
            attempts.append(
                DecisionAttempt(
                    source=decider.name,
                    outcome="accepted" if accepted else "unsure",
                    confidence=decision.confidence,
                    effective_confidence=effective,
                    value=decision.value.model_dump(mode="json"),
                )
            )
            if accepted:
                return decision.model_copy(update={"attempts": attempts})
            logger.debug(
                "Decider %r unsure on %s (confidence=%s < %.2f), trying next",
                decider.name,
                request.kind,
                effective,
                self.min_confidence,
            )

        decision = await self._fallback.decide(request)
        if decision is None:
            raise RuntimeError(
                f"Fallback decider {self._fallback.name!r} abstained on {request.kind}"
            )
        return decision.model_copy(update={"attempts": attempts})

    # ---- Typed convenience helpers ----

    async def significance(
        self,
        interaction: Interaction,
        core_values: list[str] | None = None,
        recent_contents: list[str] | None = None,
    ) -> Decision[SignificanceVerdict]:
        return await self.decide(
            SignificanceRequest(
                interaction=interaction,
                core_values=core_values or [],
                recent_contents=recent_contents or [],
            )
        )

    async def sentiment(self, text: str) -> Decision[SomaticMarker]:
        return await self.decide(SentimentRequest(text=text))

    async def contradictions(
        self,
        new_content: str,
        existing: list[MemoryEntry],
        user_aliases: list[str] | None = None,
    ) -> Decision[ContradictionVerdict]:
        return await self.decide(
            ContradictionRequest(
                new_content=new_content, existing=existing, user_aliases=user_aliases or []
            )
        )

    async def dedup(
        self, new_fact: str, existing_facts: list[MemoryEntry]
    ) -> Decision[DedupVerdict]:
        return await self.decide(DedupRequest(new_fact=new_fact, existing_facts=existing_facts))
