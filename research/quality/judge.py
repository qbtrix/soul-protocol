# judge.py — LLM-as-judge module for Soul Protocol quality validation.
# Uses HaikuCognitiveEngine to score agent responses on 6 quality dimensions.
# Supports single-response scoring and pairwise A/B comparison with position-bias mitigation.

from __future__ import annotations

import json
import random
import re
import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..haiku_engine import HaikuCognitiveEngine

# ---------------------------------------------------------------------------
# Quality dimensions
# ---------------------------------------------------------------------------


class QualityDimension(Enum):
    """Six dimensions for evaluating agent response quality."""

    MEMORY_UTILIZATION = "memory_utilization"
    PERSONALITY_CONSISTENCY = "personality_consistency"
    EMOTIONAL_AWARENESS = "emotional_awareness"
    CONTINUITY = "continuity"
    HELPFULNESS = "helpfulness"
    NATURALNESS = "naturalness"


# Short keys used in judge prompts and JSON parsing.
_DIMENSION_KEYS: dict[QualityDimension, str] = {
    QualityDimension.MEMORY_UTILIZATION: "memory",
    QualityDimension.PERSONALITY_CONSISTENCY: "personality",
    QualityDimension.EMOTIONAL_AWARENESS: "emotional",
    QualityDimension.CONTINUITY: "continuity",
    QualityDimension.HELPFULNESS: "helpfulness",
    QualityDimension.NATURALNESS: "naturalness",
}

# Human-readable descriptions for judge prompts.
_DIMENSION_DESCRIPTIONS: dict[QualityDimension, str] = {
    QualityDimension.MEMORY_UTILIZATION: (
        "Memory utilization: Does the response reference information from past interactions?"
    ),
    QualityDimension.PERSONALITY_CONSISTENCY: (
        "Personality consistency: Does the tone and style match the agent's described personality?"
    ),
    QualityDimension.EMOTIONAL_AWARENESS: (
        "Emotional awareness: Does the response acknowledge or respond to the user's emotional state?"
    ),
    QualityDimension.CONTINUITY: (
        "Continuity: Does it feel like talking to the same entity across turns?"
    ),
    QualityDimension.HELPFULNESS: (
        "Helpfulness: Is the response actually useful and relevant to the user's message?"
    ),
    QualityDimension.NATURALNESS: (
        "Naturalness: Does it sound like a real personality, not a generic bot?"
    ),
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class JudgeScore:
    """Score for a single quality dimension."""

    dimension: str
    score: float  # 1-10 scale
    reasoning: str

    def __post_init__(self) -> None:
        self.score = max(1.0, min(10.0, float(self.score)))


@dataclass
class JudgeResult:
    """Complete result of a pairwise comparison."""

    scores: list[JudgeScore]
    overall: float
    winner: str  # "soul", "baseline", or "tie"
    winner_reasoning: str

    @staticmethod
    def from_paired_scores(
        soul_scores: list[JudgeScore],
        baseline_scores: list[JudgeScore],
        winner: str,
        winner_reasoning: str,
    ) -> JudgeResult:
        """Build a JudgeResult from both sets of scores."""
        all_scores = soul_scores + baseline_scores
        mean = statistics.mean(s.score for s in all_scores) if all_scores else 0.0
        return JudgeResult(
            scores=all_scores,
            overall=mean,
            winner=winner,
            winner_reasoning=winner_reasoning,
        )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SINGLE_SCORE_PROMPT = """\
You are evaluating an AI assistant response. Score the response on a 1-10 scale for each dimension.

Context:
- Agent name: {agent_name}
- Agent personality: {personality_description}
- Conversation history:
{conversation_history}
- Facts the agent should remember: {planted_facts}
- User's current message: {user_message}

Response to evaluate:
{response}

Score the response on these dimensions (1 = terrible, 10 = exceptional):
{dimension_list}

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "scores": {{
    {score_keys_template}
  }},
  "reasoning": {{
    {reasoning_keys_template}
  }}
}}"""

_PAIRWISE_PROMPT = """\
You are evaluating two AI assistant responses. Score each response on a 1-10 scale, then pick a winner.

Important: Score BOTH responses on ALL dimensions BEFORE deciding a winner. Do not let your winner preference influence scores.

Context:
- Agent name: {agent_name}
- Agent personality: {personality_description}
- Conversation history:
{conversation_history}
- Facts the agent should remember: {planted_facts}
- User's current message: {user_message}

Response A:
{response_a}

Response B:
{response_b}

Score each response on these dimensions (1 = terrible, 10 = exceptional):
{dimension_list}

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "response_a_scores": {{
    {score_keys_template}
  }},
  "response_b_scores": {{
    {score_keys_template}
  }},
  "response_a_reasoning": {{
    {reasoning_keys_template}
  }},
  "response_b_reasoning": {{
    {reasoning_keys_template}
  }},
  "winner": "A" or "B" or "tie",
  "winner_reasoning": "Brief explanation of why this response is better overall."
}}"""


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_judge_response(text: str) -> dict[str, Any]:
    """Parse JSON from judge response, handling markdown fences and preamble.

    The LLM may wrap JSON in ```json ... ``` fences or include conversational
    text before/after the JSON object. This function extracts and parses the
    first valid JSON object found in the text.
    """
    # Strip markdown code fences if present.
    stripped = re.sub(r"```(?:json)?\s*", "", text)
    stripped = re.sub(r"```", "", stripped)
    stripped = stripped.strip()

    # Try direct parse first.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Find the first { ... } block using brace counting.
    start = stripped.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in judge response: {text[:200]}")

    depth = 0
    for i in range(start, len(stripped)):
        if stripped[i] == "{":
            depth += 1
        elif stripped[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Found JSON-like block but failed to parse: {candidate[:200]}"
                    )

    raise ValueError(f"Unbalanced braces in judge response: {text[:200]}")


# ---------------------------------------------------------------------------
# ResponseJudge
# ---------------------------------------------------------------------------


class ResponseJudge:
    """LLM-as-judge for scoring agent responses on quality dimensions.

    Uses a HaikuCognitiveEngine to evaluate responses. Supports scoring a
    single response or comparing a pair (with randomised A/B ordering to
    mitigate position bias).
    """

    def __init__(self, engine: HaikuCognitiveEngine) -> None:
        self._engine = engine

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _format_dimension_list() -> str:
        lines = []
        for i, dim in enumerate(QualityDimension, 1):
            lines.append(f"{i}. {_DIMENSION_DESCRIPTIONS[dim]}")
        return "\n".join(lines)

    @staticmethod
    def _score_keys_template() -> str:
        keys = [f'"{_DIMENSION_KEYS[d]}": <score>' for d in QualityDimension]
        return ",\n    ".join(keys)

    @staticmethod
    def _reasoning_keys_template() -> str:
        keys = [f'"{_DIMENSION_KEYS[d]}": "<brief reason>"' for d in QualityDimension]
        return ",\n    ".join(keys)

    @staticmethod
    def _format_context(context: dict[str, Any]) -> dict[str, str]:
        """Normalise context dict values to strings for prompt interpolation."""
        history = context.get("conversation_history", [])
        if isinstance(history, list):
            history_str = (
                "\n".join(
                    f"  {turn.get('role', '?')}: {turn.get('content', '')}" for turn in history
                )
                or "  (none)"
            )
        else:
            history_str = str(history)

        facts = context.get("planted_facts", [])
        if isinstance(facts, list):
            facts_str = ", ".join(str(f) for f in facts) or "(none)"
        else:
            facts_str = str(facts)

        return {
            "agent_name": str(context.get("agent_name", "Agent")),
            "personality_description": str(context.get("personality_description", "Not specified")),
            "conversation_history": history_str,
            "planted_facts": facts_str,
            "user_message": str(context.get("user_message", "")),
        }

    def _build_scores_from_dict(
        self,
        scores_dict: dict[str, Any],
        reasoning_dict: dict[str, Any],
        prefix: str = "",
    ) -> list[JudgeScore]:
        """Convert raw score/reasoning dicts to JudgeScore objects."""
        result: list[JudgeScore] = []
        for dim in QualityDimension:
            key = _DIMENSION_KEYS[dim]
            score_val = scores_dict.get(key, 5.0)
            reason = reasoning_dict.get(key, "")
            dimension_label = f"{prefix}{dim.value}" if prefix else dim.value
            # Robust score extraction: handle cases where judge returns text
            try:
                numeric_score = float(score_val)
            except (ValueError, TypeError):
                import re

                nums = re.findall(r"\b(\d+(?:\.\d+)?)\b", str(score_val))
                numeric_score = float(nums[0]) if nums else 5.0
            result.append(
                JudgeScore(
                    dimension=dimension_label,
                    score=numeric_score,
                    reasoning=str(reason),
                )
            )
        return result

    # -- public API -------------------------------------------------------

    async def score_single(
        self,
        response: str,
        context: dict[str, Any],
    ) -> list[JudgeScore]:
        """Score a single response on all quality dimensions.

        Parameters
        ----------
        response:
            The agent's response text to evaluate.
        context:
            Dict with keys: user_message, agent_name, personality_description,
            conversation_history (list of {role, content} dicts), planted_facts
            (list of strings).

        Returns
        -------
        list[JudgeScore]
            One score per quality dimension.
        """
        ctx = self._format_context(context)
        prompt = _SINGLE_SCORE_PROMPT.format(
            **ctx,
            response=response,
            dimension_list=self._format_dimension_list(),
            score_keys_template=self._score_keys_template(),
            reasoning_keys_template=self._reasoning_keys_template(),
        )

        raw = await self._engine.think(prompt)
        try:
            parsed = _parse_judge_response(raw)
            if not isinstance(parsed, dict):
                parsed = {}
        except (ValueError, json.JSONDecodeError):
            parsed = {}

        scores_dict = parsed.get("scores", {})
        reasoning_dict = parsed.get("reasoning", {})
        if not isinstance(scores_dict, dict):
            scores_dict = {}
        if not isinstance(reasoning_dict, dict):
            reasoning_dict = {}

        return self._build_scores_from_dict(scores_dict, reasoning_dict)

    async def compare_pair(
        self,
        with_soul: str,
        without_soul: str,
        context: dict[str, Any],
    ) -> JudgeResult:
        """Compare two responses and pick a winner.

        Responses are randomly assigned to positions A/B to avoid position
        bias. Scores are requested before the winner declaration to prevent
        anchoring.

        Parameters
        ----------
        with_soul:
            Response from the soul-enabled agent.
        without_soul:
            Response from the baseline agent (no soul).
        context:
            Same context dict as ``score_single``.

        Returns
        -------
        JudgeResult
            Scores for both responses, overall mean, winner, and reasoning.
        """
        # Randomise position to mitigate ordering bias.
        soul_is_a = random.random() < 0.5

        if soul_is_a:
            response_a, response_b = with_soul, without_soul
        else:
            response_a, response_b = without_soul, with_soul

        ctx = self._format_context(context)
        prompt = _PAIRWISE_PROMPT.format(
            **ctx,
            response_a=response_a,
            response_b=response_b,
            dimension_list=self._format_dimension_list(),
            score_keys_template=self._score_keys_template(),
            reasoning_keys_template=self._reasoning_keys_template(),
        )

        raw = await self._engine.think(prompt)
        try:
            parsed = _parse_judge_response(raw)
            if not isinstance(parsed, dict):
                parsed = {}
        except (ValueError, json.JSONDecodeError):
            parsed = {}

        # Extract scores for both responses.
        a_scores_dict = parsed.get("response_a_scores", {})
        b_scores_dict = parsed.get("response_b_scores", {})
        a_reasoning_dict = parsed.get("response_a_reasoning", {})
        b_reasoning_dict = parsed.get("response_b_reasoning", {})
        # Ensure dicts, not strings
        if not isinstance(a_scores_dict, dict):
            a_scores_dict = {}
        if not isinstance(b_scores_dict, dict):
            b_scores_dict = {}
        if not isinstance(a_reasoning_dict, dict):
            a_reasoning_dict = {}
        if not isinstance(b_reasoning_dict, dict):
            b_reasoning_dict = {}

        a_scores = self._build_scores_from_dict(a_scores_dict, a_reasoning_dict, prefix="a:")
        b_scores = self._build_scores_from_dict(b_scores_dict, b_reasoning_dict, prefix="b:")

        # Map winner back from A/B to soul/baseline.
        raw_winner = str(parsed.get("winner", "tie")).strip().upper()
        if raw_winner == "A":
            winner = "soul" if soul_is_a else "baseline"
        elif raw_winner == "B":
            winner = "baseline" if soul_is_a else "soul"
        else:
            winner = "tie"

        winner_reasoning = str(parsed.get("winner_reasoning", ""))

        # Assign scores to soul/baseline labels.
        if soul_is_a:
            soul_scores = a_scores
            baseline_scores = b_scores
        else:
            soul_scores = b_scores
            baseline_scores = a_scores

        # Relabel dimension prefixes to soul:/baseline: for clarity.
        for s in soul_scores:
            s.dimension = s.dimension.replace("a:", "soul:").replace("b:", "soul:")
        for s in baseline_scores:
            s.dimension = s.dimension.replace("a:", "baseline:").replace("b:", "baseline:")

        return JudgeResult.from_paired_scores(
            soul_scores=soul_scores,
            baseline_scores=baseline_scores,
            winner=winner,
            winner_reasoning=winner_reasoning,
        )
