# test_decide/conftest.py — Shared fakes for Soul Instinct tests.
# Created: feat/soul-instinct — Deterministic stand-ins for model-backed deciders,
#   a scripted CognitiveEngine, and a fake NLI cross-encoder, so the decision layer
#   can be tested end-to-end without network access or model downloads.

from __future__ import annotations

from collections.abc import Callable

from soul_protocol.runtime.decide import (
    ContradictionFinding,
    ContradictionRequest,
    ContradictionVerdict,
    Decision,
    DecisionKind,
    SignificanceRequest,
    SignificanceVerdict,
)
from soul_protocol.runtime.types import SignificanceScore


class KeywordContradictionDecider:
    """Flags memories containing ``target`` when new content contains ``trigger``."""

    def __init__(
        self,
        name: str = "keyword",
        *,
        confidence: float | None = 0.95,
        trigger: str = "vegetarian",
        target: str = "steak",
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.confidence = confidence
        self.trigger = trigger
        self.target = target
        self.error = error
        self.calls = 0

    def supports(self, kind: DecisionKind) -> bool:
        return kind == DecisionKind.CONTRADICTION

    async def decide(self, request):
        if not isinstance(request, ContradictionRequest):
            return None
        self.calls += 1
        if self.error is not None:
            raise self.error
        findings = []
        if self.trigger in request.new_content.lower():
            findings = [
                ContradictionFinding(old_memory_id=e.id, confidence=self.confidence or 0.0)
                for e in request.existing
                if self.target in e.content.lower() and not e.superseded and e.superseded_by is None
            ]
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(findings=findings),
            confidence=self.confidence,
            source=self.name,
        )


class FixedSignificanceDecider:
    """Answers every significance request with a fixed verdict."""

    def __init__(
        self, name: str = "fixed-sig", *, significant: bool = True, confidence: float = 0.9
    ) -> None:
        self.name = name
        self.significant = significant
        self.confidence = confidence
        self.calls = 0

    def supports(self, kind: DecisionKind) -> bool:
        return kind == DecisionKind.SIGNIFICANCE

    async def decide(self, request):
        if not isinstance(request, SignificanceRequest):
            return None
        self.calls += 1
        level = 1.0 if self.significant else 0.0
        return Decision(
            kind=DecisionKind.SIGNIFICANCE,
            value=SignificanceVerdict(
                score=SignificanceScore(
                    novelty=level,
                    emotional_intensity=level,
                    goal_relevance=level,
                    content_richness=level,
                ),
                overall=level,
                significant=self.significant,
            ),
            confidence=self.confidence,
            source=self.name,
        )


class ScriptedEngine:
    """CognitiveEngine whose replies come from a function of the prompt."""

    def __init__(self, reply: Callable[[str], str]) -> None:
        self._reply = reply
        self.prompts: list[str] = []

    async def think(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._reply(prompt)


class FakeCrossEncoder:
    """Stands in for sentence_transformers.CrossEncoder.

    ``logits`` maps (premise, hypothesis) -> [contradiction, entailment, neutral].
    Unknown pairs are confidently neutral.
    """

    def __init__(self, logits: dict[tuple[str, str], list[float]]) -> None:
        self._logits = logits
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [self._logits.get(tuple(p), [-4.0, -4.0, 4.0]) for p in pairs]


class FakeEmbedder:
    """EmbeddingProvider stand-in: texts in ``related`` share one direction.

    Every text listed in ``related`` embeds to axis 0; every other distinct text
    gets its own axis, so related texts have cosine 1.0 with each other and
    everything else has cosine 0.0.
    """

    DIMS = 64

    def __init__(self, related: set[str]) -> None:
        self._related = related
        self._axes: dict[str, int] = {}
        self.batches: list[list[str]] = []

    def _vector(self, text: str) -> list[float]:
        axis = 0 if text in self._related else self._axes.setdefault(text, len(self._axes) + 1)
        vec = [0.0] * self.DIMS
        vec[axis] = 1.0
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [self._vector(t) for t in texts]
