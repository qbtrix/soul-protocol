# memory/contradiction.py — Semantic contradiction detection for memory pipeline.
# Created: v0.4.0 — Heuristic and LLM-powered contradiction detection.
#   Heuristic mode uses embedding similarity + negation patterns + entity-attribute
#   conflict detection. LLM mode delegates to CognitiveEngine for top-5 similar
#   memories. When contradiction detected, old memory is marked superseded=True.
# Updated: v0.4.x — Added verb-based fact pattern detection (_VERB_FACT_PATTERNS,
#   _extract_verb_facts, _check_verb_fact_conflict) to catch location/employer changes
#   like "User lives in NYC" vs "User moved to Amsterdam" that Jaccard similarity
#   alone misses due to low token overlap (~0.15 < 0.3 threshold). Second pass in
#   detect_heuristic checks ALL existing memories for verb-fact conflicts, bypassing
#   the Jaccard filter entirely for these structured fact assertions.

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from soul_protocol.runtime.memory.dedup import _jaccard_similarity
from soul_protocol.runtime.types import MemoryEntry

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine

logger = logging.getLogger(__name__)

# Negation patterns: words/phrases that flip meaning
_NEGATION_PAIRS: list[tuple[re.Pattern[str], re.Pattern[str]]] = [
    (re.compile(r"\bis\b", re.I), re.compile(r"\bis not\b|\bisn'?t\b", re.I)),
    (
        re.compile(r"\blikes?\b|\bloves?\b|\bprefers?\b", re.I),
        re.compile(r"\bhates?\b|\bdislikes?\b|\bdoesn'?t like\b", re.I),
    ),
    (
        re.compile(r"\bworks? (?:at|for)\b", re.I),
        re.compile(r"\bleft\b|\bquit\b|\bno longer works?\b", re.I),
    ),
    (re.compile(r"\bcan\b", re.I), re.compile(r"\bcan(?:no|'?)t\b", re.I)),
    (re.compile(r"\bdoes\b", re.I), re.compile(r"\bdoes(?:n'?t| not)\b", re.I)),
    (re.compile(r"\bhas\b", re.I), re.compile(r"\bhas(?:n'?t| not)\b|\bno longer has\b", re.I)),
    (re.compile(r"\bwill\b", re.I), re.compile(r"\bwon'?t\b|\bwill not\b", re.I)),
    (re.compile(r"\btrue\b", re.I), re.compile(r"\bfalse\b", re.I)),
    (re.compile(r"\byes\b", re.I), re.compile(r"\bno\b", re.I)),
]

# Entity-attribute patterns for extracting "X is Y" style assertions
_ENTITY_ATTR_RE = re.compile(
    r"(?:user(?:'s)?|their|the)\s+(\w[\w\s]{0,20}?)\s+is\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)

# Verb-based fact patterns for location/employer/role assertions that use action
# verbs rather than "is". Each tuple: (compiled regex, attribute_name_for_conflict_key).
# For single-value patterns, group 1 = value. For the role pattern, group 1 = role
# and group 2 = employer — handled specially in _extract_verb_facts.
_VERB_FACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:user|i)\s+(?:live?s?|resides?)\s+in\s+(.+?)(?:\.|,|$)", re.I), "location"),
    (
        re.compile(
            r"(?:user|i)\s+(?:moved?|relocated?|moved? to)\s+(?:to\s+)?(.+?)(?:\.|,|$)", re.I
        ),
        "location",
    ),
    (re.compile(r"(?:user|i)\s+(?:is\s+)?based\s+in\s+(.+?)(?:\.|,|$)", re.I), "location"),
    (
        re.compile(
            r"(?:user|i)\s+(?:works?\s+(?:at|for)|joined?|started?\s+at)\s+(.+?)(?:\.|,|$)", re.I
        ),
        "employer",
    ),
    (
        re.compile(r"(?:user|i)\s+(?:is\s+)?(?:a\s+)?(.+?)\s+(?:at|@)\s+(.+?)(?:\.|,|$)", re.I),
        "role",
    ),
]


def _extract_verb_facts(content: str) -> dict[str, str]:
    """Extract verb-based fact assertions from content.

    Returns a dict mapping attribute key (e.g. "location", "employer") to the
    normalised value found. For the role pattern, the key is "role" and the
    value is "role_value @ employer_value".

    Only the first match per attribute key is kept (earlier = more specific).
    """
    facts: dict[str, str] = {}
    for pattern, attr_key in _VERB_FACT_PATTERNS:
        match = pattern.search(content)
        if match is None:
            continue
        if attr_key == "role" and match.lastindex is not None and match.lastindex >= 2:
            # Two capture groups: role and employer
            value = f"{match.group(1).strip().lower()} @ {match.group(2).strip().lower()}"
        else:
            value = match.group(1).strip().lower()
        # Keep first match per key (don't overwrite with a later, weaker pattern)
        if attr_key not in facts:
            facts[attr_key] = value
    return facts


class ContradictionResult:
    """Result of a contradiction check between two memories."""

    __slots__ = ("is_contradiction", "old_memory_id", "new_content", "reason", "confidence")

    def __init__(
        self,
        is_contradiction: bool,
        old_memory_id: str = "",
        new_content: str = "",
        reason: str = "",
        confidence: float = 0.0,
    ) -> None:
        self.is_contradiction = is_contradiction
        self.old_memory_id = old_memory_id
        self.new_content = new_content
        self.reason = reason
        self.confidence = confidence


class ContradictionDetector:
    """Detects semantic contradictions between new and existing memories.

    Two modes:
    - Heuristic (no LLM): Uses token similarity to find similar memories,
      then checks for negation patterns or different values for the same
      entity-attribute pairs.
    - LLM mode: Asks CognitiveEngine to evaluate top-5 similar memories
      for contradictions.
    """

    def __init__(
        self,
        engine: CognitiveEngine | None = None,
        similarity_threshold: float = 0.3,
    ) -> None:
        """Initialize the contradiction detector.

        Args:
            engine: Optional CognitiveEngine for LLM-powered detection.
                When None, uses heuristic mode only.
            similarity_threshold: Minimum Jaccard similarity to consider
                two memories as potential contradictions (default 0.3).
        """
        self._engine = engine
        self._similarity_threshold = similarity_threshold

    def _find_similar(
        self, content: str, candidates: list[MemoryEntry], top_k: int = 5
    ) -> list[tuple[float, MemoryEntry]]:
        """Find the top-k most similar non-superseded memories."""
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in candidates:
            if entry.superseded:
                continue
            if entry.superseded_by is not None:
                continue
            sim = _jaccard_similarity(content, entry.content)
            if sim >= self._similarity_threshold:
                scored.append((sim, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def _check_negation(self, content_a: str, content_b: str) -> tuple[bool, str]:
        """Check if two pieces of content contain negation-flipped statements.

        Returns (is_negated, reason).
        """
        for pos_pattern, neg_pattern in _NEGATION_PAIRS:
            a_has_pos = bool(pos_pattern.search(content_a))
            a_has_neg = bool(neg_pattern.search(content_a))
            b_has_pos = bool(pos_pattern.search(content_b))
            b_has_neg = bool(neg_pattern.search(content_b))

            # One has positive form (without negation), other has negated form.
            # Note: the negated form may also match the positive pattern (e.g.,
            # "is not" contains "is"), so we check neg first as the more specific match.
            a_is_negated = a_has_neg
            b_is_negated = b_has_neg
            a_is_positive = a_has_pos and not a_has_neg
            b_is_positive = b_has_pos and not b_has_neg

            if a_is_positive and b_is_negated:
                return (
                    True,
                    f"Negation detected: '{pos_pattern.pattern}' vs '{neg_pattern.pattern}'",
                )
            if b_is_positive and a_is_negated:
                return (
                    True,
                    f"Negation detected: '{pos_pattern.pattern}' vs '{neg_pattern.pattern}'",
                )
        return False, ""

    def _check_entity_attribute_conflict(self, content_a: str, content_b: str) -> tuple[bool, str]:
        """Check if two contents assert different values for the same entity attribute.

        E.g., "User's language is Python" vs "User's language is Rust".
        """
        attrs_a = _ENTITY_ATTR_RE.findall(content_a)
        attrs_b = _ENTITY_ATTR_RE.findall(content_b)

        for attr_a, val_a in attrs_a:
            attr_a_norm = attr_a.strip().lower()
            val_a_norm = val_a.strip().lower()
            for attr_b, val_b in attrs_b:
                attr_b_norm = attr_b.strip().lower()
                val_b_norm = val_b.strip().lower()
                if attr_a_norm == attr_b_norm and val_a_norm != val_b_norm:
                    return True, (
                        f"Entity-attribute conflict: '{attr_a_norm}' "
                        f"was '{val_a_norm}', now '{val_b_norm}'"
                    )
        return False, ""

    def _check_verb_fact_conflict(self, content_a: str, content_b: str) -> tuple[bool, str]:
        """Check if two contents assert different values for the same verb-based fact.

        Handles location/employer/role patterns that _ENTITY_ATTR_RE misses, e.g.:
        - "User lives in NYC" vs "User moved to Amsterdam" → location conflict
        - "User works at Google" vs "User joined Stripe" → employer conflict

        Returns (is_conflict, reason).
        """
        facts_a = _extract_verb_facts(content_a)
        facts_b = _extract_verb_facts(content_b)

        for key in facts_a:
            if key in facts_b and facts_a[key] != facts_b[key]:
                return True, (
                    f"Verb-fact conflict: '{key}' was '{facts_a[key]}', now '{facts_b[key]}'"
                )
        return False, ""

    async def detect_heuristic(
        self, new_content: str, existing: list[MemoryEntry]
    ) -> list[ContradictionResult]:
        """Detect contradictions using heuristic methods (no LLM).

        Finds similar memories and checks for negation patterns or
        entity-attribute conflicts. Then performs a second pass over ALL
        existing memories (bypassing the Jaccard threshold) to catch verb-based
        fact conflicts (location, employer, role) where token overlap is too low
        to reach the similarity threshold.

        Args:
            new_content: The content of the new memory to check.
            existing: List of existing memories to compare against.

        Returns:
            List of ContradictionResult for each detected contradiction.
        """
        similar = self._find_similar(new_content, existing)
        results: list[ContradictionResult] = []

        # Track IDs already flagged so the second pass doesn't double-report.
        flagged_ids: set[str] = set()

        for sim_score, entry in similar:
            # Check negation
            is_neg, neg_reason = self._check_negation(new_content, entry.content)
            if is_neg:
                results.append(
                    ContradictionResult(
                        is_contradiction=True,
                        old_memory_id=entry.id,
                        new_content=new_content,
                        reason=neg_reason,
                        confidence=min(sim_score + 0.2, 1.0),
                    )
                )
                flagged_ids.add(entry.id)
                continue

            # Check entity-attribute conflict
            is_conflict, conflict_reason = self._check_entity_attribute_conflict(
                new_content, entry.content
            )
            if is_conflict:
                results.append(
                    ContradictionResult(
                        is_contradiction=True,
                        old_memory_id=entry.id,
                        new_content=new_content,
                        reason=conflict_reason,
                        confidence=min(sim_score + 0.1, 1.0),
                    )
                )
                flagged_ids.add(entry.id)

        # Second pass: verb-fact conflict check over ALL non-superseded memories.
        # This bypasses the Jaccard threshold so short location/employer phrases
        # ("User lives in NYC" vs "User moved to Amsterdam", Jaccard ≈ 0.15) are
        # still caught even though they share few tokens.
        new_verb_facts = _extract_verb_facts(new_content)
        if new_verb_facts:
            for entry in existing:
                if entry.superseded or entry.superseded_by is not None:
                    continue
                if entry.id in flagged_ids:
                    continue
                is_vf_conflict, vf_reason = self._check_verb_fact_conflict(
                    new_content, entry.content
                )
                if is_vf_conflict:
                    # Use a fixed baseline confidence since Jaccard wasn't used here.
                    results.append(
                        ContradictionResult(
                            is_contradiction=True,
                            old_memory_id=entry.id,
                            new_content=new_content,
                            reason=vf_reason,
                            confidence=0.8,
                        )
                    )
                    flagged_ids.add(entry.id)

        return results

    async def detect_llm(
        self, new_content: str, existing: list[MemoryEntry]
    ) -> list[ContradictionResult]:
        """Detect contradictions using LLM (CognitiveEngine).

        Sends the top-5 similar memories to the engine and asks it to
        identify contradictions.

        Args:
            new_content: The content of the new memory to check.
            existing: List of existing memories to compare against.

        Returns:
            List of ContradictionResult for each detected contradiction.

        Raises:
            RuntimeError: If no CognitiveEngine is configured.
        """
        if self._engine is None:
            raise RuntimeError("LLM mode requires a CognitiveEngine")

        similar = self._find_similar(new_content, existing)
        if not similar:
            return []

        # Build prompt for the engine
        memories_text = "\n".join(
            f"[{i + 1}] (id={entry.id}) {entry.content}" for i, (_, entry) in enumerate(similar)
        )
        prompt = (
            f'New memory: "{new_content}"\n\n'
            f"Existing memories:\n{memories_text}\n\n"
            "Which existing memories (if any) does the new memory contradict? "
            "A contradiction means the new information directly conflicts with "
            "or replaces the old information. Respond with ONLY the numbers "
            "of contradicted memories (e.g., '1, 3') or 'none' if no contradictions."
        )

        try:
            response = await self._engine.think(prompt)
            response_lower = response.strip().lower()

            if response_lower == "none" or not response_lower:
                return []

            # Parse the response for memory indices
            results: list[ContradictionResult] = []
            for match in re.finditer(r"\d+", response):
                idx = int(match.group()) - 1
                if 0 <= idx < len(similar):
                    sim_score, entry = similar[idx]
                    results.append(
                        ContradictionResult(
                            is_contradiction=True,
                            old_memory_id=entry.id,
                            new_content=new_content,
                            reason=f"LLM detected contradiction: {response.strip()}",
                            confidence=min(sim_score + 0.3, 1.0),
                        )
                    )
            return results
        except Exception:
            logger.warning("LLM contradiction detection failed, falling back to heuristic")
            return await self.detect_heuristic(new_content, existing)

    async def detect(
        self, new_content: str, existing: list[MemoryEntry]
    ) -> list[ContradictionResult]:
        """Detect contradictions using the best available method.

        Uses LLM mode if a CognitiveEngine is available, otherwise
        falls back to heuristic detection.

        Args:
            new_content: The content of the new memory to check.
            existing: List of existing memories to compare against.

        Returns:
            List of ContradictionResult for each detected contradiction.
        """
        if self._engine is not None:
            return await self.detect_llm(new_content, existing)
        return await self.detect_heuristic(new_content, existing)
