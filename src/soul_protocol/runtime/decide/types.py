# decide/types.py — Typed request/verdict models for the Soul Instinct decision layer.
# Created: feat/soul-instinct — Every decision the memory pipeline makes (is this
#   significant? what mood? does it contradict? is it a duplicate?) gets one typed
#   request model and one typed verdict model, so any backend (heuristic rules, a
#   local classifier, a hosted decision model such as Jev, or an LLM) can answer
#   the same question in the same shape. ``Decision`` wraps the verdict with the
#   backend's confidence and name so callers can gate on confidence.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from soul_protocol.runtime.types import (
    Interaction,
    MemoryEntry,
    SignificanceScore,
    SomaticMarker,
)


class DecisionKind(StrEnum):
    """The questions the memory pipeline asks a decider."""

    SIGNIFICANCE = "significance"
    SENTIMENT = "sentiment"
    CONTRADICTION = "contradiction"
    DEDUP = "dedup"


# ============ Requests ============


class SignificanceRequest(BaseModel):
    """Is this interaction worth storing as an episodic memory?"""

    kind: Literal[DecisionKind.SIGNIFICANCE] = DecisionKind.SIGNIFICANCE
    interaction: Interaction
    core_values: list[str] = Field(default_factory=list)
    recent_contents: list[str] = Field(default_factory=list)


class SentimentRequest(BaseModel):
    """What is the emotional tone of this text?"""

    kind: Literal[DecisionKind.SENTIMENT] = DecisionKind.SENTIMENT
    text: str


class ContradictionRequest(BaseModel):
    """Which existing memories does the new content contradict?"""

    kind: Literal[DecisionKind.CONTRADICTION] = DecisionKind.CONTRADICTION
    new_content: str
    existing: list[MemoryEntry] = Field(default_factory=list)
    # Names that mean "the user" in memory text (InstinctSettings.user_aliases).
    user_aliases: list[str] = Field(default_factory=list)


class DedupRequest(BaseModel):
    """Should this fact be created, merged into an existing fact, or skipped?"""

    kind: Literal[DecisionKind.DEDUP] = DecisionKind.DEDUP
    new_fact: str
    existing_facts: list[MemoryEntry] = Field(default_factory=list)


DecisionRequest = Annotated[
    SignificanceRequest | SentimentRequest | ContradictionRequest | DedupRequest,
    Field(discriminator="kind"),
]


# ============ Verdicts ============


class SignificanceVerdict(BaseModel):
    """Significance gate outcome: per-dimension scores plus the final call."""

    score: SignificanceScore
    overall: float = Field(ge=0.0, le=1.0)
    significant: bool


class ContradictionFinding(BaseModel):
    """One existing memory the new content contradicts."""

    old_memory_id: str
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ContradictionVerdict(BaseModel):
    """All contradictions found for a piece of new content (empty = none)."""

    findings: list[ContradictionFinding] = Field(default_factory=list)


DedupAction = Literal["CREATE", "SKIP", "MERGE"]


class DedupVerdict(BaseModel):
    """Dedup outcome. ``target_id`` is set for SKIP and MERGE, None for CREATE."""

    action: DedupAction
    target_id: str | None = None


V = TypeVar("V", SignificanceVerdict, SomaticMarker, ContradictionVerdict, DedupVerdict)

AttemptOutcome = Literal["accepted", "unsure", "abstained", "error"]


class DecisionAttempt(BaseModel):
    """What one decider in a DeciderChain said about a request.

    Attributes:
        source: Decider name.
        outcome: ``accepted`` (answer used), ``unsure`` (answered below the
            confidence bar), ``abstained`` (returned None) or ``error`` (raised).
        confidence: The decider's raw confidence, if it answered.
        effective_confidence: Confidence after per-soul calibration.
        value: The decider's verdict as a plain dict, if it answered. Kept
            for unsure answers so a later review can learn from them.
    """

    source: str
    outcome: AttemptOutcome
    confidence: float | None = None
    effective_confidence: float | None = None
    value: dict | None = None


class Decision(BaseModel, Generic[V]):
    """A decider's answer to one request.

    Attributes:
        kind: Which question was answered.
        value: The typed verdict.
        confidence: How sure the backend is (0.0-1.0). ``None`` means the
            backend does not produce a calibrated confidence (e.g. the
            rule-based heuristics); a ``DeciderChain`` only accepts such an
            answer from its final fallback.
        source: Name of the decider that produced the answer.
        reason: Optional short human-readable explanation.
        attempts: Set by DeciderChain — every non-fallback decider consulted
            before this answer, in order.
    """

    kind: DecisionKind
    value: V
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str
    reason: str = ""
    attempts: list[DecisionAttempt] = Field(default_factory=list)

    def most_confident_unsure(self) -> DecisionAttempt | None:
        """The unsure attempt with the highest confidence, if any decider was unsure."""
        unsure = [a for a in self.attempts if a.outcome == "unsure" and a.value is not None]
        return max(unsure, key=lambda a: a.confidence or 0.0, default=None)
