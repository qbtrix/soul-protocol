# cognitive/engine.py — CognitiveEngine protocol, HeuristicEngine, CognitiveProcessor.
# Updated: 2026-03-13 — Removed "from" from _PROFILE_KEYWORDS and "may" from
#   _EVENT_KEYWORDS to prevent false positive classifications.
# Updated: Phase 2 memory-runtime-v2
#   - extract_facts() now classifies each fact into a MemoryCategory using heuristics
#   - extract_facts() generates abstract (L0) for each fact (~400 chars of content)
#   - extract_facts() computes salience from SignificanceScore when available
#   - extract_entities() passes metadata dict with source_memory_id and extracted_at
#     to graph edge creation (returned in entity dicts for caller to forward)
# Updated: Fixed import ordering — moved logger assignment after all imports
#   (stdlib, then project imports, then logger).

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from soul_protocol.runtime.cognitive.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    FACT_EXTRACTION_PROMPT,
    REFLECT_PROMPT,
    SELF_REFLECTION_PROMPT,
    SENTIMENT_PROMPT,
    SIGNIFICANCE_PROMPT,
)
from soul_protocol.runtime.types import (
    Interaction,
    MemoryCategory,
    MemoryEntry,
    MemoryType,
    ReflectionResult,
    SelfImage,
    SignificanceScore,
    SomaticMarker,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.self_model import SelfModelManager

logger = logging.getLogger(__name__)


def _heuristic_sentiment(text: str) -> SomaticMarker:
    """Lazy wrapper for v0.2.0 sentiment heuristic (avoids circular import)."""
    from soul_protocol.runtime.memory.sentiment import detect_sentiment

    return detect_sentiment(text)


def _heuristic_significance(
    interaction: Interaction,
    core_values: list[str],
    recent_contents: list[str],
) -> SignificanceScore:
    """Lazy wrapper for v0.2.0 significance heuristic (avoids circular import)."""
    from soul_protocol.runtime.memory.attention import compute_significance

    return compute_significance(interaction, core_values, recent_contents)


# ---------------------------------------------------------------------------
# CognitiveEngine protocol — the ONE interface consumers provide
# ---------------------------------------------------------------------------


@runtime_checkable
class CognitiveEngine(Protocol):
    """Interface for the soul's cognitive processing.

    The consumer provides an LLM via this interface. The soul uses it
    to think about emotions, significance, facts, and identity.

    Simplest implementation:
        class MyCognitive:
            async def think(self, prompt: str) -> str:
                return await my_llm_client.complete(prompt)
    """

    async def think(self, prompt: str) -> str: ...


# ---------------------------------------------------------------------------
# HeuristicEngine — zero-dependency fallback
# ---------------------------------------------------------------------------


class HeuristicEngine:
    """Zero-dependency fallback that wraps v0.2.0 heuristic modules.

    Used when no LLM is available (offline, testing, cost-constrained).
    Routes prompts to appropriate heuristic based on [TASK:xxx] markers
    and returns structured JSON mimicking LLM output format.
    """

    async def think(self, prompt: str) -> str:
        """Route prompt to appropriate heuristic based on task marker."""
        task = _extract_task_marker(prompt)

        if task == "sentiment":
            return self._sentiment(prompt)
        elif task == "significance":
            return self._significance(prompt)
        elif task == "extract_facts":
            return self._extract_facts(prompt)
        elif task == "extract_entities":
            return self._extract_entities(prompt)
        elif task == "self_reflection":
            return self._self_reflection(prompt)
        elif task == "reflect":
            return json.dumps(
                {
                    "themes": [],
                    "summaries": [],
                    "promote": [],
                    "emotional_patterns": "insufficient data for reflection",
                    "self_insight": "",
                }
            )

        return json.dumps({"error": f"unknown task: {task}"})

    def _sentiment(self, prompt: str) -> str:
        """Extract text from sentiment prompt and run heuristic."""
        text = _extract_field(prompt, "Text:")
        marker = _heuristic_sentiment(text)
        return json.dumps(
            {
                "valence": marker.valence,
                "arousal": marker.arousal,
                "label": marker.label,
            }
        )

    def _significance(self, prompt: str) -> str:
        """Run simplified significance heuristic from prompt text."""
        user_input = _extract_field(prompt, "User:")
        somatic = _heuristic_sentiment(user_input)
        emotional = min(1.0, somatic.arousal + abs(somatic.valence) * 0.3)
        return json.dumps(
            {
                "novelty": 0.5,
                "emotional_intensity": round(emotional, 3),
                "goal_relevance": 0.3,
                "reasoning": "heuristic estimate",
            }
        )

    def _extract_facts(self, prompt: str) -> str:
        """Run simplified fact extraction from prompt text."""
        user_input = _extract_field(prompt, "User:")
        facts: list[dict] = []
        name_match = re.search(r"my name is (\w+)", user_input, re.IGNORECASE)
        if name_match:
            facts.append(
                {
                    "content": f"User's name is {name_match.group(1)}",
                    "importance": 9,
                }
            )
        return json.dumps(facts)

    def _extract_entities(self, prompt: str) -> str:
        """Run simplified entity extraction from prompt text."""
        return json.dumps([])

    def _self_reflection(self, prompt: str) -> str:
        """Return minimal self-reflection."""
        return json.dumps(
            {
                "self_images": [],
                "insights": "heuristic mode — limited self-reflection",
                "relationship_notes": {},
            }
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_task_marker(prompt: str) -> str:
    """Extract [TASK:xxx] marker from prompt text."""
    match = re.search(r"\[TASK:(\w+)\]", prompt)
    return match.group(1) if match else "unknown"


def _extract_field(prompt: str, field: str) -> str:
    """Extract the value after a field label in the prompt.

    Captures everything after 'Field:' until the next blank line,
    next field label (line starting with uppercase + colon), or end of string.
    """
    pattern = re.compile(
        rf"^\s*{re.escape(field)}\s*(.*?)(?:\n\n|\n\s*[A-Z][\w\s]*:|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(prompt)
    return match.group(1).strip() if match else ""


def _parse_json(text: str) -> dict | list:
    """Extract JSON from LLM response, handling markdown fences and preamble.

    Tries in order:
    1. Direct JSON parse
    2. Extract from ```json ... ``` blocks
    3. Find first { or [ and parse from there
    """
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced block
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find first { or [
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue

    raise json.JSONDecodeError("No valid JSON found", text, 0)


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value between low and high."""
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Extraction taxonomy classification (Phase 2 — heuristic, no LLM)
# ---------------------------------------------------------------------------

# Keyword sets for heuristic category classification
_PREFERENCE_KEYWORDS = {"likes", "prefers", "favorite", "favourite", "love", "loves",
                        "prefer", "dislikes", "hates", "hate", "dislike"}
_EVENT_KEYWORDS = {"yesterday", "today", "tomorrow", "last week", "next week",
                   "last month", "next month", "monday", "tuesday", "wednesday",
                   "thursday", "friday", "saturday", "sunday", "january", "february",
                   "march", "april", "june", "july", "august", "september",
                   "october", "november", "december", "morning", "evening",
                   "afternoon", "meeting", "event", "scheduled", "deadline"}
_PROFILE_KEYWORDS = {"name is", "works at", "work for", "lives in",
                     "is a", "is an", "age", "born", "occupation", "role"}


def classify_memory_category(content: str) -> MemoryCategory | None:
    """Classify a memory's content into a MemoryCategory using keyword heuristics.

    No LLM required. Returns None for content that doesn't clearly match
    a category (backward-compatible default for semantic memories).

    Args:
        content: The memory content string to classify.

    Returns:
        A MemoryCategory or None if no clear match.
    """
    lower = content.lower()

    # Check preference keywords
    if any(kw in lower for kw in _PREFERENCE_KEYWORDS):
        return MemoryCategory.PREFERENCE

    # Check for person-name / entity patterns (capitalized words after "User's")
    if re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", content):
        # Looks like a proper name → entity
        return MemoryCategory.ENTITY

    # Check event keywords (time/date references)
    if any(kw in lower for kw in _EVENT_KEYWORDS):
        return MemoryCategory.EVENT

    # Check profile keywords
    if any(kw in lower for kw in _PROFILE_KEYWORDS):
        return MemoryCategory.PROFILE

    # Default: don't set category (None for backward compat)
    return None


def generate_abstract(content: str) -> str:
    """Generate a short abstract (L0) from memory content.

    Heuristic approach: extracts the first sentence, truncated to ~400 chars
    (~100 tokens). This serves as a semantic fingerprint for progressive
    content loading.

    Args:
        content: The full memory content.

    Returns:
        A truncated abstract string.
    """
    # Take first sentence (split on sentence-ending punctuation)
    first_sentence = re.split(r"[.!?\n]", content, maxsplit=1)[0].strip()
    # Truncate to ~400 chars
    if len(first_sentence) > 400:
        # Truncate at last word boundary before 400 chars
        truncated = first_sentence[:400].rsplit(" ", 1)[0]
        return truncated + "..."
    return first_sentence


def compute_salience(significance: SignificanceScore) -> float:
    """Map a SignificanceScore to a salience value (0.0-1.0).

    Weighted combination of significance dimensions:
      - novelty: 0.3
      - emotional_intensity: 0.3
      - goal_relevance: 0.25
      - content_richness: 0.15

    Args:
        significance: The SignificanceScore from the attention gate.

    Returns:
        Salience value clamped to [0.0, 1.0].
    """
    raw = (
        significance.novelty * 0.3
        + significance.emotional_intensity * 0.3
        + significance.goal_relevance * 0.25
        + significance.content_richness * 0.15
    )
    return min(1.0, raw)


# ---------------------------------------------------------------------------
# CognitiveProcessor — internal orchestrator
# ---------------------------------------------------------------------------


class CognitiveProcessor:
    """Internal orchestrator that uses a CognitiveEngine for psychology tasks.

    Handles prompt construction, response parsing, validation, and
    fallback to heuristics on parse failure.

    Two modes:
    - Heuristic-only: calls v0.2.0 functions directly for identical behavior
    - LLM-enhanced: constructs prompts, sends to engine, parses responses,
      falls back to heuristic on failure
    """

    def __init__(
        self,
        engine: CognitiveEngine,
        fallback: HeuristicEngine | None = None,
        fact_extractor: Callable[..., list[MemoryEntry]] | None = None,
        entity_extractor: Callable[..., list[dict]] | None = None,
    ) -> None:
        self._engine = engine
        self._fallback = fallback
        self._is_heuristic_only = isinstance(engine, HeuristicEngine)
        self._fact_extractor = fact_extractor
        self._entity_extractor = entity_extractor

    async def detect_sentiment(self, text: str) -> SomaticMarker:
        """Detect emotional sentiment from text."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            return _heuristic_sentiment(text)

        prompt = SENTIMENT_PROMPT.format(text=text)
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return SomaticMarker(
                valence=_clamp(data["valence"], -1.0, 1.0),
                arousal=_clamp(data["arousal"], 0.0, 1.0),
                label=data.get("label", "neutral"),
            )
        except Exception:
            logger.warning("LLM sentiment detection failed, falling back to heuristic")
            if self._fallback:
                return _heuristic_sentiment(text)
            return SomaticMarker()

    async def assess_significance(
        self,
        interaction: Interaction,
        core_values: list[str],
        recent_contents: list[str],
    ) -> SignificanceScore:
        """Assess how significant an interaction is for episodic storage."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            return _heuristic_significance(interaction, core_values, recent_contents)

        prompt = SIGNIFICANCE_PROMPT.format(
            values=", ".join(core_values) if core_values else "none specified",
            recent_summaries=("\n".join(f"- {r[:100]}" for r in recent_contents[-5:]) or "none"),
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return SignificanceScore(
                novelty=_clamp(data["novelty"], 0.0, 1.0),
                emotional_intensity=_clamp(data["emotional_intensity"], 0.0, 1.0),
                goal_relevance=_clamp(data["goal_relevance"], 0.0, 1.0),
            )
        except Exception:
            logger.warning(
                "LLM significance assessment failed, falling back to heuristic"
            )
            if self._fallback:
                return _heuristic_significance(interaction, core_values, recent_contents)
            return SignificanceScore()

    async def extract_facts(
        self,
        interaction: Interaction,
        existing_facts: list[MemoryEntry] | None = None,
        significance: SignificanceScore | None = None,
    ) -> list[MemoryEntry]:
        """Extract semantic facts from an interaction.

        Phase 2 enhancements:
          - Classifies each fact into a MemoryCategory via heuristic keywords
          - Generates an abstract (L0) from the fact content
          - Computes salience from the interaction's SignificanceScore
        """
        # Fast path: delegate to MemoryManager's heuristic extractor
        if self._is_heuristic_only and self._fact_extractor:
            entries = self._fact_extractor(interaction)
            self._enrich_facts(entries, significance)
            return entries

        prompt = FACT_EXTRACTION_PROMPT.format(
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            if not isinstance(data, list):
                data = data.get("facts", [])

            entries: list[MemoryEntry] = []
            for item in data:
                entries.append(
                    MemoryEntry(
                        type=MemoryType.SEMANTIC,
                        content=item["content"],
                        importance=min(10, max(1, int(item.get("importance", 5)))),
                    )
                )
            self._enrich_facts(entries, significance)
            return entries
        except Exception:
            logger.warning(
                "LLM fact extraction failed, falling back to heuristic"
            )
            if self._fact_extractor:
                entries = self._fact_extractor(interaction)
                self._enrich_facts(entries, significance)
                return entries
            return []

    @staticmethod
    def _enrich_facts(
        entries: list[MemoryEntry],
        significance: SignificanceScore | None = None,
    ) -> None:
        """Enrich extracted facts with category, abstract, and salience.

        Mutates entries in-place. Called after both heuristic and LLM
        extraction paths.

        Args:
            entries: List of MemoryEntry objects to enrich.
            significance: Optional SignificanceScore for salience computation.
        """
        salience = compute_salience(significance) if significance else 0.5
        for entry in entries:
            entry.category = classify_memory_category(entry.content)
            entry.abstract = generate_abstract(entry.content)
            entry.salience = salience

    async def extract_entities(
        self,
        interaction: Interaction,
        source_memory_id: str | None = None,
    ) -> list[dict]:
        """Extract named entities from an interaction.

        Phase 2 enhancement: each entity dict includes an ``edge_metadata``
        field with source_memory_id and extracted_at for graph edge provenance.

        Args:
            interaction: The interaction to extract entities from.
            source_memory_id: Optional ID of the episodic memory that triggered
                this extraction, used for edge metadata provenance.
        """
        edge_metadata = {
            "source_memory_id": source_memory_id or "",
            "extracted_at": datetime.now().isoformat(),
        }

        # Fast path: delegate to MemoryManager's heuristic extractor
        if self._is_heuristic_only and self._entity_extractor:
            entities = self._entity_extractor(interaction)
            for e in entities:
                e["edge_metadata"] = edge_metadata
            return entities

        prompt = ENTITY_EXTRACTION_PROMPT.format(
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            if not isinstance(data, list):
                data = data.get("entities", [])

            entities: list[dict] = []
            for item in data:
                entities.append(
                    {
                        "name": item["name"],
                        "type": item.get("type", "unknown"),
                        "relation": item.get("relation"),
                        "edge_metadata": edge_metadata,
                    }
                )
            return entities
        except Exception:
            logger.warning(
                "LLM entity extraction failed, falling back to heuristic"
            )
            if self._entity_extractor:
                entities = self._entity_extractor(interaction)
                for e in entities:
                    e["edge_metadata"] = edge_metadata
                return entities
            return []

    async def update_self_model(
        self,
        interaction: Interaction,
        facts: list[MemoryEntry],
        self_model: SelfModelManager,
    ) -> None:
        """Update the soul's self-concept based on an interaction."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            self_model.update_from_interaction(interaction, facts)
            return

        current_images = self_model.get_active_self_images()
        images_text = (
            "\n".join(
                f"- {img.domain}: confidence={img.confidence:.2f}, evidence={img.evidence_count}"
                for img in current_images
            )
            or "none yet"
        )

        recent_text = f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"

        prompt = SELF_REFLECTION_PROMPT.format(
            soul_name="soul",
            current_self_images=images_text,
            recent_episodes=recent_text,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)

            for img_data in data.get("self_images", []):
                domain = img_data.get("domain", "")
                if domain:
                    existing = self_model._self_images.get(domain)
                    evidence = (existing.evidence_count + 1) if existing else 1
                    confidence = _clamp(img_data.get("confidence", 0.5), 0.0, 1.0)
                    self_model._self_images[domain] = SelfImage(
                        domain=domain,
                        confidence=confidence,
                        evidence_count=evidence,
                    )

            for entity, note in data.get("relationship_notes", {}).items():
                if entity and note:
                    self_model._relationship_notes[entity] = note

        except Exception:
            logger.warning(
                "LLM self-model update failed, falling back to heuristic"
            )
            self_model.update_from_interaction(interaction, facts)

    async def reflect(
        self,
        recent_episodes: list[Any],
        current_self_model: dict,
        soul_name: str = "soul",
    ) -> ReflectionResult | None:
        """Run a reflection/consolidation pass (LLM-only).

        Returns None in heuristic-only mode — genuine reflection requires
        an LLM to reason about patterns across episodes.
        """
        if self._is_heuristic_only:
            return None

        episode_texts: list[str] = []
        for ep in recent_episodes[:20]:
            if isinstance(ep, MemoryEntry):
                episode_texts.append(f"- [{ep.created_at}] {ep.content}")
            elif isinstance(ep, dict):
                episode_texts.append(f"- {ep.get('content', str(ep))}")
            else:
                episode_texts.append(f"- {ep}")

        self_model_text = json.dumps(current_self_model, indent=2, default=str)

        prompt = REFLECT_PROMPT.format(
            soul_name=soul_name,
            count=len(episode_texts),
            episodes="\n".join(episode_texts) or "no recent episodes",
            self_model=self_model_text,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return ReflectionResult(
                themes=data.get("themes", []),
                summaries=data.get("summaries", []),
                emotional_patterns=data.get("emotional_patterns", ""),
                self_insight=data.get("self_insight", ""),
            )
        except Exception:
            logger.warning("LLM reflection failed, returning None")
            return None
