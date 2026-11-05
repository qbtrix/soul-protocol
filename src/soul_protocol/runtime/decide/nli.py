# decide/nli.py — NLIContradictionDecider: local, offline contradiction detection.
# Created: feat/soul-instinct — Uses a small Natural Language Inference cross-encoder
#   (default cross-encoder/nli-deberta-v3-xsmall) via sentence-transformers. Runs on
#   the user's machine, so no memory text leaves it.
#   Requires: pip install 'soul-protocol[embeddings-st]'.
#
#   SNLI-style NLI models assume both sentences describe the same scene, so they
#   label *unrelated* facts as contradictions ("User likes cricket" vs "User loves
#   steak" → 0.99). Two guards make them usable for memory:
#     1. Relatedness gate — only memories whose embedding cosine similarity to the
#        new content reaches ``relatedness_threshold`` are judged; unrelated ones
#        are confidently "no contradiction". (Measured on real models: true
#        contradictions scored 0.56-0.78, unrelated false alarms 0.45-0.49.)
#     2. Both directions — some contradictions only register one way (Delhi →
#        Mumbai: 0.36 forward, 0.99 backward), so the max of the two is used.
#   First-person text ("I'm vegetarian") and the user's names (user_aliases, e.g.
#   "Shekhar loves dosa") are normalized to "User ..." first; a pronoun or name
#   mismatch alone otherwise defeats the relatedness gate (0.42 vs 0.71 measured).
#   Models are loaded lazily on first use and inference runs in a worker thread.

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Sequence
from typing import Any

from soul_protocol.runtime.decide.candidates import DEFAULT_MAX_CANDIDATES, select_candidates
from soul_protocol.runtime.decide.types import (
    ContradictionFinding,
    ContradictionRequest,
    ContradictionVerdict,
    Decision,
    DecisionKind,
    DecisionRequest,
)
from soul_protocol.runtime.embeddings.similarity import cosine_similarity
from soul_protocol.runtime.types import MemoryEntry

DEFAULT_NLI_MODEL: str = "cross-encoder/nli-deberta-v3-xsmall"
DEFAULT_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
DEFAULT_RELATEDNESS_THRESHOLD: float = 0.5
# Output order of the sentence-transformers NLI cross-encoders.
DEFAULT_LABEL_ORDER: tuple[str, ...] = ("contradiction", "entailment", "neutral")

_INSTALL_HINT = "Install with: pip install 'soul-protocol[embeddings-st]'"

# Stored facts are phrased "User ...", raw user messages "I ...". The pronoun
# mismatch alone drops embedding similarity below the relatedness gate, so both
# sides are normalized to the stored form before comparison.
_FIRST_PERSON: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bI'm\b|\bI am\b", re.IGNORECASE), "User is"),
    (re.compile(r"\bI've\b|\bI have\b", re.IGNORECASE), "User has"),
    (re.compile(r"\bI'll\b|\bI will\b", re.IGNORECASE), "User will"),
    (re.compile(r"\bI'd\b", re.IGNORECASE), "User would"),
    (re.compile(r"\bI was\b", re.IGNORECASE), "User was"),
    (re.compile(r"\b(?:my|mine)\b", re.IGNORECASE), "User's"),
    (re.compile(r"\bI\b|\bme\b", re.IGNORECASE), "User"),
]


def _third_person(text: str, aliases: Sequence[str] = ()) -> str:
    """Normalize first person and the user's names to the stored "User" form."""
    for pattern, replacement in _FIRST_PERSON:
        text = pattern.sub(replacement, text)
    for alias in aliases:
        if alias.strip():
            text = re.sub(rf"\b{re.escape(alias.strip())}\b", "User", text, flags=re.IGNORECASE)
    return text


def _softmax(logits: Sequence[float]) -> list[float]:
    peak = max(logits)
    exps = [math.exp(x - peak) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


class NLIContradictionDecider:
    """Contradiction-only decider backed by a local NLI cross-encoder.

    Args:
        model_name: HuggingFace cross-encoder id.
        model: Pre-built model exposing ``predict(pairs) -> rows of logits``.
            Mainly for tests and for sharing one loaded model between souls.
        label_order: Label for each logit column; must include "contradiction".
        threshold: Contradiction probability at which a pair is flagged.
        max_candidates: Maximum existing memories compared per request.
        relatedness_threshold: Minimum embedding cosine similarity for a memory to
            be judged at all. ``None`` disables the gate (not recommended with
            SNLI-trained models).
        embedder: EmbeddingProvider for the relatedness gate (anything with
            ``embed_batch``). Defaults to a lazily loaded
            ``SentenceTransformerProvider("all-MiniLM-L6-v2")``.
        device: Torch device passed to CrossEncoder (None = auto).
    """

    name = "nli"

    def __init__(
        self,
        model_name: str = DEFAULT_NLI_MODEL,
        *,
        model: Any | None = None,
        label_order: Sequence[str] = DEFAULT_LABEL_ORDER,
        threshold: float = 0.5,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        relatedness_threshold: float | None = DEFAULT_RELATEDNESS_THRESHOLD,
        embedder: Any | None = None,
        device: str | None = None,
    ) -> None:
        if "contradiction" not in label_order:
            raise ValueError("label_order must include 'contradiction'")
        self._model_name = model_name
        self._model = model
        self._contradiction_index = list(label_order).index("contradiction")
        self._threshold = threshold
        self._max_candidates = max_candidates
        self._relatedness_threshold = relatedness_threshold
        self._embedder = embedder
        self._device = device

    def supports(self, kind: DecisionKind) -> bool:
        return kind == DecisionKind.CONTRADICTION

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise ImportError(
                    f"NLIContradictionDecider requires sentence-transformers. {_INSTALL_HINT}"
                ) from e
            self._model = CrossEncoder(self._model_name, device=self._device)
        return self._model

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            try:
                import sentence_transformers  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    f"NLIContradictionDecider's relatedness gate requires "
                    f"sentence-transformers. {_INSTALL_HINT}"
                ) from e
            from soul_protocol.runtime.embeddings.sentence_transformer import (
                SentenceTransformerProvider,
            )

            self._embedder = SentenceTransformerProvider(
                DEFAULT_EMBEDDING_MODEL, device=self._device
            )
        return self._embedder

    async def _related(
        self, new_content: str, candidates: list[MemoryEntry], aliases: Sequence[str]
    ) -> list[MemoryEntry]:
        if self._relatedness_threshold is None:
            return candidates
        embedder = self._get_embedder()
        vectors = await asyncio.to_thread(
            embedder.embed_batch,
            [_third_person(new_content, aliases)]
            + [_third_person(e.content, aliases) for e in candidates],
        )
        new_vec = vectors[0]
        return [
            entry
            for entry, vec in zip(candidates, vectors[1:], strict=True)
            if cosine_similarity(new_vec, vec) >= self._relatedness_threshold
        ]

    async def decide(self, request: DecisionRequest) -> Decision[ContradictionVerdict] | None:
        if not isinstance(request, ContradictionRequest):
            return None
        candidates = select_candidates(request.new_content, request.existing, self._max_candidates)
        if candidates:
            candidates = await self._related(request.new_content, candidates, request.user_aliases)
        if not candidates:
            return Decision(
                kind=DecisionKind.CONTRADICTION,
                value=ContradictionVerdict(),
                confidence=1.0,
                source=self.name,
                reason="no related live memories to compare",
            )

        model = self._get_model()
        new = _third_person(request.new_content, request.user_aliases)
        old = [_third_person(e.content, request.user_aliases) for e in candidates]
        pairs = [(o, new) for o in old] + [(new, o) for o in old]
        rows = await asyncio.to_thread(model.predict, pairs)
        n = len(candidates)

        findings: list[ContradictionFinding] = []
        certainty = 1.0
        for i, entry in enumerate(candidates):
            p_contra = max(
                _softmax([float(x) for x in rows[i]])[self._contradiction_index],
                _softmax([float(x) for x in rows[i + n]])[self._contradiction_index],
            )
            certainty = min(certainty, max(p_contra, 1.0 - p_contra))
            if p_contra >= self._threshold:
                findings.append(
                    ContradictionFinding(
                        old_memory_id=entry.id,
                        reason=f"NLI contradiction probability {p_contra:.2f}",
                        confidence=p_contra,
                    )
                )
        findings.sort(key=lambda f: f.confidence, reverse=True)
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(findings=findings),
            confidence=certainty,
            source=self.name,
        )
