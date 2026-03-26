# runtime/evaluation.py — Rubric-based self-evaluation for soul interactions.
# Created: 2026-03-18 — MVP: heuristic evaluator, default rubrics, domain stats.
# Updated: 2026-03-26 — Recalibrated heuristic scoring for realistic conversation scores:
#   - completeness: 20-word threshold (was 40), so 2-sentence responses score ~1.0
#   - relevance: uses len(user_tokens) as denominator (was max), so thorough
#     agent responses aren't penalized for extra context
#   - specificity: counts 6+ char words as specific content, *2 multiplier
#   - evolution trigger: streak threshold 0.55 (was 0.70), trigger avg 0.55 (was 0.75)
#   A solid technical conversation now scores ~0.65-0.80 and can trigger evolution.
# Updated: 2026-03-22 — Added create_learning_event() to Evaluator.

from __future__ import annotations

from soul_protocol.spec.learning import LearningEvent

from .types import (
    CriterionResult,
    Interaction,
    Rubric,
    RubricCriterion,
    RubricResult,
)

# Score thresholds for generating learning events.
HIGH_SCORE_THRESHOLD: float = 0.8
LOW_SCORE_THRESHOLD: float = 0.3

# ============ Stop Words ============
# Small set for relevance calculation. Intentionally self-contained to avoid
# coupling with memory/self_model.py.

STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "not", "with", "this", "that", "was",
    "are", "be", "has", "had", "do", "did", "will", "can", "i", "you",
    "he", "she", "we", "they", "my", "your", "me",
})

# ============ Default Criteria ============

DEFAULT_CRITERIA: list[RubricCriterion] = [
    RubricCriterion(
        name="completeness",
        description="Agent provided a substantive response addressing the user's request",
        weight=1.0,
    ),
    RubricCriterion(
        name="relevance",
        description="Agent response is directly relevant to what the user asked",
        weight=1.0,
    ),
    RubricCriterion(
        name="helpfulness",
        description="Agent response would be useful to the user",
        weight=0.8,
    ),
]

# ============ Default Rubrics ============
# One rubric per seed domain from self_model.py. Each gets the 3 default
# criteria plus 1-2 domain-specific ones.


def _make_rubric(name: str, domain: str, extras: list[RubricCriterion]) -> Rubric:
    """Build a rubric from the shared defaults plus domain-specific criteria."""
    return Rubric(
        name=name,
        domain=domain,
        criteria=list(DEFAULT_CRITERIA) + extras,
    )


DEFAULT_RUBRICS: dict[str, Rubric] = {
    "technical_helper": _make_rubric(
        "technical_helper", "technical_helper",
        [
            RubricCriterion(
                name="specificity",
                description="Response includes specific technical details, code, or commands",
            ),
        ],
    ),
    "creative_writer": _make_rubric(
        "creative_writer", "creative_writer",
        [
            RubricCriterion(
                name="originality",
                description="Response shows creative or novel expression",
            ),
        ],
    ),
    "knowledge_guide": _make_rubric(
        "knowledge_guide", "knowledge_guide",
        [
            RubricCriterion(
                name="clarity",
                description="Response explains concepts clearly and accessibly",
            ),
        ],
    ),
    "problem_solver": _make_rubric(
        "problem_solver", "problem_solver",
        [
            RubricCriterion(
                name="specificity",
                description="Response includes specific steps, diagnoses, or actionable solutions",
            ),
        ],
    ),
    "creative_collaborator": _make_rubric(
        "creative_collaborator", "creative_collaborator",
        [
            RubricCriterion(
                name="originality",
                description="Response contributes novel ideas or unexpected angles",
            ),
        ],
    ),
    "emotional_companion": _make_rubric(
        "emotional_companion", "emotional_companion",
        [
            RubricCriterion(
                name="empathy",
                description="Response acknowledges and validates the user's feelings",
            ),
        ],
    ),
}


# ============ Heuristic Scoring Functions ============


def _score_completeness(agent_output: str) -> float:
    """Longer responses score higher, up to 20 words = 1.0.

    Recalibrated: 40 words was too harsh — a solid 2-sentence response
    (15-20 words) should score near 1.0, not 0.5.
    """
    return min(1.0, len(agent_output.split()) / 20)


def _score_relevance(user_input: str, agent_output: str) -> float:
    """Token overlap between input and output, excluding stop words.

    Recalibrated: uses min(len) as denominator instead of max(len) so
    that a thorough agent response with extra context doesn't get penalized
    for having more tokens than the user's question.
    """
    user_tokens = {
        w.lower() for w in user_input.split() if w.lower() not in STOP_WORDS
    }
    agent_tokens = {
        w.lower() for w in agent_output.split() if w.lower() not in STOP_WORDS
    }
    if not user_tokens or not agent_tokens:
        return 0.0
    shared = user_tokens & agent_tokens
    # Use user_tokens as denominator — did the agent address the user's terms?
    return min(1.0, len(shared) / len(user_tokens))


def _score_helpfulness(completeness: float, relevance: float, sentiment_positive: bool) -> float:
    """Average of completeness and relevance with a positive-sentiment boost."""
    sentiment_boost = 1.2 if sentiment_positive else 1.0
    return min(1.0, (completeness + relevance) / 2 * sentiment_boost)


def _score_specificity(agent_output: str) -> float:
    """Score based on concrete/specific content markers.

    Recalibrated: also counts longer words (6+ chars) as likely-specific
    content, not just uppercase/digits/code-like tokens. Conversational
    but substantive responses should score ~0.5-0.7, not ~0.05.
    """
    words = agent_output.split()
    if not words:
        return 0.0
    specific_count = 0
    for word in words:
        # Has uppercase letters (proper nouns, acronyms)
        if any(c.isupper() for c in word[1:] if c.isalpha()):
            specific_count += 1
        # Has numbers
        elif any(c.isdigit() for c in word):
            specific_count += 1
        # Code-like tokens
        elif any(ch in word for ch in (".", "()", "_")):
            specific_count += 1
        # Longer words are more likely to be specific/technical
        elif len(word) >= 6:
            specific_count += 1
    return min(1.0, specific_count / max(len(words), 1) * 2)


def _score_empathy(agent_output: str) -> float:
    """Check for empathy marker words."""
    empathy_markers = {
        "understand", "feel", "sorry", "glad", "appreciate",
        "hear", "difficult", "tough", "hard", "care",
        "support", "here", "listen", "valid", "okay",
    }
    output_lower = agent_output.lower()
    count = sum(1 for marker in empathy_markers if marker in output_lower)
    return min(1.0, count / 3)


def _detect_positive_sentiment(text: str) -> bool:
    """Simple heuristic: more positive words than negative."""
    positive = {"great", "good", "excellent", "helpful", "thanks", "love", "awesome", "perfect", "nice", "wonderful"}
    negative = {"bad", "wrong", "terrible", "awful", "hate", "useless", "broken", "fail", "error", "bug"}
    lower = text.lower()
    pos_count = sum(1 for w in positive if w in lower)
    neg_count = sum(1 for w in negative if w in lower)
    return pos_count > neg_count


# ============ Heuristic Evaluator ============


def heuristic_evaluate(interaction: Interaction, rubric: Rubric) -> RubricResult:
    """Evaluate an interaction against a rubric using heuristic scoring.

    No LLM required — uses word counts, token overlap, and keyword detection.
    Good enough for bootstrapping the evolution system before an LLM evaluator
    is wired in.
    """
    user_input = interaction.user_input
    agent_output = interaction.agent_output

    completeness = _score_completeness(agent_output)
    relevance = _score_relevance(user_input, agent_output)
    sentiment_positive = _detect_positive_sentiment(agent_output)
    helpfulness = _score_helpfulness(completeness, relevance, sentiment_positive)

    # Pre-compute shared scores so criterion lookup is fast
    score_map: dict[str, float] = {
        "completeness": completeness,
        "relevance": relevance,
        "helpfulness": helpfulness,
        "specificity": _score_specificity(agent_output),
        "originality": 0.5,  # unknowable heuristically
        "clarity": (completeness + relevance) / 2,  # rough proxy
        "empathy": _score_empathy(agent_output),
    }

    criterion_results: list[CriterionResult] = []
    total_weight = 0.0
    weighted_sum = 0.0

    for criterion in rubric.criteria:
        score = score_map.get(criterion.name, 0.5)
        criterion_results.append(
            CriterionResult(
                criterion=criterion.name,
                passed=score >= 0.5,
                score=score,
                reasoning=f"Heuristic score for {criterion.name}",
            )
        )
        total_weight += criterion.weight
        weighted_sum += score * criterion.weight

    overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Generate learning string
    if criterion_results:
        best = max(criterion_results, key=lambda r: r.score)
        worst = min(criterion_results, key=lambda r: r.score)
        learning = (
            f"Scored {overall_score:.0%} on {rubric.name}. "
            f"Strongest: {best.criterion}. Weakest: {worst.criterion}."
        )
    else:
        learning = f"Scored {overall_score:.0%} on {rubric.name}."

    return RubricResult(
        rubric_id=rubric.id,
        overall_score=overall_score,
        criterion_results=criterion_results,
        learning=learning,
    )


# ============ Evaluator ============


class Evaluator:
    """Rubric-based evaluator with history tracking and evolution triggers.

    Wraps heuristic_evaluate with domain auto-selection, result history,
    and streak detection for the evolution system.
    """

    def __init__(self, rubrics: dict[str, Rubric] | None = None) -> None:
        self._rubrics: dict[str, Rubric] = rubrics or dict(DEFAULT_RUBRICS)
        self._history: list[RubricResult] = []
        self._max_history: int = 100

    async def evaluate(
        self,
        interaction: Interaction,
        rubric: Rubric | None = None,
        domain: str | None = None,
    ) -> RubricResult:
        """Evaluate an interaction against a rubric.

        Auto-selects rubric from domain if not provided. Falls back to
        technical_helper if the domain is unknown.
        """
        if rubric is None:
            domain_key = domain or "technical_helper"
            rubric = self._rubrics.get(
                domain_key, self._rubrics.get("technical_helper")
            )
            # Final safety net — should never happen with DEFAULT_RUBRICS
            if rubric is None:  # pragma: no cover
                rubric = list(self._rubrics.values())[0]

        result = heuristic_evaluate(interaction, rubric)
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return result

    def get_domain_stats(self, domain: str) -> dict:
        """Get average score, count, and streak for a domain."""
        domain_results = [
            r for r in self._history if r.rubric_id == domain
        ]
        if not domain_results:
            return {"domain": domain, "count": 0, "avg_score": 0.0, "streak": 0}

        scores = [r.overall_score for r in domain_results]

        # Calculate streak of consecutive above-average scores.
        # Threshold 0.55 is calibrated for heuristic mode where a solid
        # conversational exchange scores ~0.6-0.8. LLM evaluators
        # naturally score higher, so this threshold works for both.
        streak = 0
        for score in reversed(scores):
            if score >= 0.55:
                streak += 1
            else:
                break

        return {
            "domain": domain,
            "count": len(scores),
            "avg_score": sum(scores) / len(scores),
            "streak": streak,
        }

    def check_evolution_triggers(self) -> list[dict]:
        """Detect patterns in evaluation history that should trigger evolution."""
        triggers: list[dict] = []
        seen_domains: set[str] = set()
        for result in self._history:
            seen_domains.add(result.rubric_id)

        for domain in seen_domains:
            stats = self.get_domain_stats(domain)
            if stats["streak"] >= 5 and stats["avg_score"] >= 0.55:
                triggers.append({
                    "domain": domain,
                    "trigger": "high_performance_streak",
                    "streak": stats["streak"],
                    "avg_score": stats["avg_score"],
                    "reason": (
                        f"Consistently high performance in {domain} "
                        f"({stats['streak']} consecutive high scores, "
                        f"avg {stats['avg_score']:.2f})"
                    ),
                })
        return triggers

    def create_learning_event(
        self,
        result: RubricResult,
        interaction_id: str | None = None,
        domain: str | None = None,
        skill_id: str | None = None,
    ) -> LearningEvent | None:
        """Create a LearningEvent from a notably high or low evaluation result."""
        score = result.overall_score
        if score >= HIGH_SCORE_THRESHOLD:
            confidence = min(1.0, 0.5 + (score - HIGH_SCORE_THRESHOLD) * 2.5)
            lesson = f"Success pattern: {result.learning}"
        elif score <= LOW_SCORE_THRESHOLD:
            confidence = min(1.0, 0.5 + (LOW_SCORE_THRESHOLD - score) * 2.5)
            lesson = f"Failure pattern: {result.learning}"
        else:
            return None
        return LearningEvent(
            trigger_interaction_id=interaction_id,
            lesson=lesson,
            domain=domain or result.rubric_id,
            confidence=confidence,
            skill_id=skill_id,
            evaluation_score=score,
        )

    def to_dict(self) -> dict:
        """Serialize evaluator state for persistence."""
        return {
            "history": [r.model_dump(mode="json") for r in self._history],
        }

    @classmethod
    def from_dict(
        cls, data: dict, rubrics: dict[str, Rubric] | None = None
    ) -> Evaluator:
        """Restore evaluator from serialized state."""
        evaluator = cls(rubrics=rubrics)
        for entry in data.get("history", []):
            evaluator._history.append(RubricResult.model_validate(entry))
        return evaluator
