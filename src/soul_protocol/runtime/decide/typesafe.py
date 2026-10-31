# decide/typesafe.py — JevDecider: TypeSafe AI's Jev decision model as a Soul decider.
# Created: feat/soul-instinct — Optional, hosted backend. Jev answers typed questions
#   (bool / pick-one / small rubric) with calibrated per-field confidence instead of
#   generating text. Uses Pydantic AI's TypeSafe integration, where each question is
#   a Pydantic model whose field docstrings are the questions. Requires
#   ``pip install "pydantic-ai-slim[typesafe]"`` and TYPESAFE_API_KEY. Memory text is
#   sent to TypeSafe's API, so only attach this decider with the user's consent.

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from soul_protocol.runtime.decide.candidates import select_candidates
from soul_protocol.runtime.decide.types import (
    ContradictionFinding,
    ContradictionRequest,
    ContradictionVerdict,
    Decision,
    DecisionKind,
    DecisionRequest,
    SignificanceRequest,
    SignificanceVerdict,
)
from soul_protocol.runtime.memory.attention import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.memory.search import tokenize
from soul_protocol.runtime.types import SignificanceScore

DEFAULT_JEV_MODEL: str = "typesafe:jev-latest"
DEFAULT_JEV_MAX_CANDIDATES: int = 10
RUBRIC_MAX: int = 4

# (state, question model) -> (answer, per-field confidence)
JevRunner = Callable[[str, type[BaseModel]], Awaitable[tuple[BaseModel, dict[str, float]]]]

Rubric = Literal[0, 1, 2, 3, 4]


class ConflictQuestion(BaseModel):
    """Compare an OLD memory about the user with a NEW statement from the conversation."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    contradicts: bool
    """Does the NEW statement contradict or replace the OLD memory, so the OLD memory is no longer true?"""


class SignificanceQuestion(BaseModel):
    """Decide whether this conversation turn is worth storing as a long-term memory."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    novelty: Rubric
    """How new is this information compared to the recent memories? 0 = already known, 4 = completely new."""
    emotional_intensity: Rubric
    """How emotionally strong is the user's message? 0 = neutral, 4 = very intense."""
    goal_relevance: Rubric
    """How relevant is this turn to the soul's core values? 0 = unrelated, 4 = central."""
    content_richness: Rubric
    """How many concrete facts, names, dates or numbers does it contain? 0 = none, 4 = many."""


def _pydantic_ai_runner(model: str) -> JevRunner:
    try:
        from pydantic_ai import Agent
    except ImportError as e:
        raise ImportError(
            "JevDecider requires Pydantic AI with the TypeSafe extra. "
            'Install with: pip install "pydantic-ai-slim[typesafe]"'
        ) from e

    agents: dict[type[BaseModel], Any] = {}

    async def run(state: str, output_type: type[BaseModel]) -> tuple[BaseModel, dict[str, float]]:
        agent = agents.get(output_type)
        if agent is None:
            agent = agents[output_type] = Agent(model, output_type=output_type)
        result = await agent.run(state)
        details = getattr(result.response, "provider_details", None) or {}
        return result.output, dict(details.get("confidence") or {})

    return run


class JevDecider:
    """Contradiction + significance decider backed by TypeSafe's Jev.

    Args:
        model: Pydantic AI model string. Pin a version (e.g. ``typesafe:jev-1.13.0``)
            once thresholds are tuned; ``jev-latest`` is a moving alias.
        runner: Override how questions are sent (tests, custom clients). Defaults
            to a Pydantic AI Agent per question type.
        max_candidates: Maximum existing memories checked per contradiction request.
        significance_threshold: Overall-significance bar for ``significant``.
    """

    name = "jev"

    def __init__(
        self,
        model: str = DEFAULT_JEV_MODEL,
        *,
        runner: JevRunner | None = None,
        max_candidates: int = DEFAULT_JEV_MAX_CANDIDATES,
        significance_threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
    ) -> None:
        self._model = model
        self._runner = runner
        self._max_candidates = max_candidates
        self._significance_threshold = significance_threshold

    def supports(self, kind: DecisionKind) -> bool:
        return kind in (DecisionKind.CONTRADICTION, DecisionKind.SIGNIFICANCE)

    def _run(self) -> JevRunner:
        if self._runner is None:
            self._runner = _pydantic_ai_runner(self._model)
        return self._runner

    async def decide(self, request: DecisionRequest) -> Decision | None:
        if isinstance(request, ContradictionRequest):
            return await self._contradiction(request)
        if isinstance(request, SignificanceRequest):
            return await self._significance(request)
        return None

    async def _contradiction(self, request: ContradictionRequest) -> Decision[ContradictionVerdict]:
        candidates = select_candidates(request.new_content, request.existing, self._max_candidates)
        if not candidates:
            return Decision(
                kind=DecisionKind.CONTRADICTION,
                value=ContradictionVerdict(),
                confidence=1.0,
                source=self.name,
                reason="no live memories to compare",
            )
        run = self._run()
        answers = await asyncio.gather(
            *(
                run(f"OLD: {entry.content}\nNEW: {request.new_content}", ConflictQuestion)
                for entry in candidates
            )
        )

        findings: list[ContradictionFinding] = []
        confidences: list[float] = []
        for entry, (answer, conf) in zip(candidates, answers, strict=True):
            c = conf.get("contradicts")
            if c is None:
                return self._unsure_contradiction()
            confidences.append(c)
            if isinstance(answer, ConflictQuestion) and answer.contradicts:
                findings.append(
                    ContradictionFinding(
                        old_memory_id=entry.id, reason="Jev judged contradiction", confidence=c
                    )
                )
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(findings=findings),
            confidence=min(confidences),
            source=self.name,
        )

    def _unsure_contradiction(self) -> Decision[ContradictionVerdict]:
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(),
            confidence=None,
            source=self.name,
            reason="Jev returned no confidence",
        )

    async def _significance(self, request: SignificanceRequest) -> Decision[SignificanceVerdict]:
        interaction = request.interaction
        recent = "\n".join(f"- {r}" for r in request.recent_contents[-5:]) or "none"
        state = (
            f"Soul's core values: {', '.join(request.core_values) or 'none specified'}\n"
            f"Recent memories:\n{recent}\n\n"
            f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"
        )
        answer, conf = await self._run()(state, SignificanceQuestion)
        if not isinstance(answer, SignificanceQuestion):
            raise TypeError(f"Jev returned {type(answer).__name__}, expected SignificanceQuestion")
        score = SignificanceScore(
            novelty=answer.novelty / RUBRIC_MAX,
            emotional_intensity=answer.emotional_intensity / RUBRIC_MAX,
            goal_relevance=answer.goal_relevance / RUBRIC_MAX,
            content_richness=answer.content_richness / RUBRIC_MAX,
        )
        token_count = len(tokenize(f"{interaction.user_input} {interaction.agent_output}"))
        field_conf = [conf[f] for f in SignificanceQuestion.model_fields if f in conf]
        return Decision(
            kind=DecisionKind.SIGNIFICANCE,
            value=SignificanceVerdict(
                score=score,
                overall=min(1.0, overall_significance(score, token_count=token_count)),
                significant=is_significant(
                    score, threshold=self._significance_threshold, token_count=token_count
                ),
            ),
            confidence=min(field_conf)
            if len(field_conf) == len(SignificanceQuestion.model_fields)
            else None,
            source=self.name,
        )
