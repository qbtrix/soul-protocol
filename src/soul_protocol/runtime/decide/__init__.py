# decide/__init__.py — Soul Instinct: pluggable, confidence-aware decision layer.
# Created: feat/soul-instinct — Exports the Decider protocol, typed request/verdict
#   models, the rule-based HeuristicDecider, the confidence-gated DeciderChain, and
#   the model-backed deciders: NLIContradictionDecider (local, offline),
#   EngineDecider (any CognitiveEngine LLM) and JevDecider (TypeSafe's hosted
#   decision model). Heavy optional dependencies are imported lazily on first use.

from __future__ import annotations

from soul_protocol.runtime.decide.chain import DEFAULT_MIN_CONFIDENCE, DeciderChain
from soul_protocol.runtime.decide.cognitive import CognitiveDecider
from soul_protocol.runtime.decide.engine import EngineDecider
from soul_protocol.runtime.decide.heuristic import HeuristicDecider
from soul_protocol.runtime.decide.nli import NLIContradictionDecider
from soul_protocol.runtime.decide.personality import modulated_thresholds
from soul_protocol.runtime.decide.protocol import Decider
from soul_protocol.runtime.decide.review import InstinctReviewReport, review_instincts
from soul_protocol.runtime.decide.types import (
    ContradictionFinding,
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
from soul_protocol.runtime.decide.typesafe import JevDecider

__all__ = [
    "DEFAULT_MIN_CONFIDENCE",
    "CognitiveDecider",
    "ContradictionFinding",
    "ContradictionRequest",
    "ContradictionVerdict",
    "Decider",
    "DeciderChain",
    "Decision",
    "DecisionAttempt",
    "DecisionKind",
    "DecisionRequest",
    "DedupRequest",
    "DedupVerdict",
    "EngineDecider",
    "HeuristicDecider",
    "InstinctReviewReport",
    "JevDecider",
    "NLIContradictionDecider",
    "SentimentRequest",
    "SignificanceRequest",
    "SignificanceVerdict",
    "modulated_thresholds",
    "review_instincts",
]
