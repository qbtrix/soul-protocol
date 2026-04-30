# eval/scoring.py — Scorers for the soul-aware eval framework.
# Created: 2026-04-29 (#160) — One async scorer per scoring kind. Returns a
#   ScoreOutcome (score 0-1, passed bool, details dict). Scorers are pure
#   functions of (soul, case, output) — no side effects on the soul. The
#   judge scorer is the only one that requires an engine; it returns a
#   "skipped" outcome when no engine is configured rather than failing.

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.memory.dedup import _jaccard_similarity
from soul_protocol.runtime.types import MemoryEntry, Mood

from .schema import (
    EvalCase,
    JudgeScoring,
    KeywordScoring,
    RegexScoring,
    SemanticScoring,
    StructuralScoring,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.soul import Soul


@dataclass
class ScoreOutcome:
    """Result of scoring one case.

    ``score`` is a normalized [0, 1] number. ``passed`` is True when
    score >= the scorer's threshold and the case actually ran.
    ``skipped`` indicates the scorer could not run (e.g. judge with no
    engine); ``passed`` is False and ``score`` is 0.0 in that case.
    """

    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False


# ---------------------------------------------------------------------------
# Result envelope passed to scorers
# ---------------------------------------------------------------------------


@dataclass
class CaseExecution:
    """Captured output from running one case before scoring.

    ``output_text`` is the rendered text the soul produced (or the
    flattened recall results). ``recall_results`` is non-empty only for
    recall-mode cases. ``mood_before/after`` and ``energy_before/after``
    snapshot soul state around the case so structural scoring can ask
    "did mood change to X."
    """

    output_text: str
    recall_results: list[MemoryEntry] = field(default_factory=list)
    mood_before: Mood = Mood.NEUTRAL
    mood_after: Mood = Mood.NEUTRAL
    energy_before: float = 100.0
    energy_after: float = 100.0


# ---------------------------------------------------------------------------
# Keyword
# ---------------------------------------------------------------------------


def score_keyword(
    case: EvalCase,
    execution: CaseExecution,
    spec: KeywordScoring,
) -> ScoreOutcome:
    """Case-insensitive substring match.

    With ``mode="all"`` the score is the fraction of keywords that
    matched and the case passes only when every keyword matches at the
    threshold's level. With ``mode="any"`` the score is binary — 1.0 if
    any keyword matches, else 0.0.
    """
    text = execution.output_text.lower()
    hits = [kw for kw in spec.expected if kw.lower() in text]
    matched = len(hits)
    total = max(1, len(spec.expected))

    if spec.mode == "all":
        score = matched / total
    else:  # "any"
        score = 1.0 if hits else 0.0

    return ScoreOutcome(
        score=score,
        passed=score >= spec.threshold,
        details={
            "mode": spec.mode,
            "matched": hits,
            "missing": [kw for kw in spec.expected if kw.lower() not in text],
            "threshold": spec.threshold,
        },
    )


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------


def score_regex(
    case: EvalCase,
    execution: CaseExecution,
    spec: RegexScoring,
) -> ScoreOutcome:
    """Python regex match against the output."""
    try:
        pattern = re.compile(spec.pattern, re.MULTILINE | re.DOTALL)
    except re.error as e:
        return ScoreOutcome(
            score=0.0,
            passed=False,
            details={"error": f"regex compile failed: {e}", "pattern": spec.pattern},
        )

    match = pattern.search(execution.output_text)
    score = 1.0 if match else 0.0
    return ScoreOutcome(
        score=score,
        passed=score >= spec.threshold,
        details={
            "pattern": spec.pattern,
            "matched": bool(match),
            "match_text": match.group(0) if match else None,
        },
    )


# ---------------------------------------------------------------------------
# Semantic (Jaccard token overlap)
# ---------------------------------------------------------------------------


def score_semantic(
    case: EvalCase,
    execution: CaseExecution,
    spec: SemanticScoring,
) -> ScoreOutcome:
    """Jaccard-with-containment token overlap.

    Reuses the soul's own dedup similarity so eval semantics match the
    similarity scoring used inside the memory pipeline.
    """
    score = _jaccard_similarity(execution.output_text, spec.expected)
    return ScoreOutcome(
        score=score,
        passed=score >= spec.threshold,
        details={
            "expected": spec.expected,
            "similarity": round(score, 4),
            "threshold": spec.threshold,
        },
    )


# ---------------------------------------------------------------------------
# Judge (LLM-as-judge)
# ---------------------------------------------------------------------------


_JUDGE_PROMPT = """You are evaluating an AI agent's response.

Criteria:
{criteria}

Agent input:
{message}

Agent output:
{output}

Score the output from 0.0 (does not meet criteria at all) to 1.0
(fully meets criteria). Return JSON only — no other text:

{{"score": <0.0-1.0>, "reasoning": "<one sentence>"}}
"""


_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


async def score_judge(
    case: EvalCase,
    execution: CaseExecution,
    spec: JudgeScoring,
    engine: CognitiveEngine | None,
) -> ScoreOutcome:
    """LLM-as-judge scoring.

    When no engine is configured the case is marked ``skipped`` (not
    failed) so a CI run that lacks API credentials can still validate
    the rest of the eval suite. When the judge call fails or returns
    unparseable output, score 0.0 with details explaining why.
    """
    if engine is None:
        return ScoreOutcome(
            score=0.0,
            passed=False,
            skipped=True,
            details={
                "reason": "no engine configured — judge scoring requires a CognitiveEngine",
            },
        )

    prompt = _JUDGE_PROMPT.format(
        criteria=spec.criteria.strip(),
        message=case.inputs.message,
        output=execution.output_text,
    )
    try:
        raw = await engine.think(prompt)
    except Exception as e:  # pragma: no cover — network / engine errors
        return ScoreOutcome(
            score=0.0,
            passed=False,
            details={"error": f"engine.think raised: {e}"},
        )

    parsed = _parse_judge_response(raw)
    if parsed is None:
        return ScoreOutcome(
            score=0.0,
            passed=False,
            details={"error": "judge response not parseable", "raw": raw[:500]},
        )

    score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
    return ScoreOutcome(
        score=score,
        passed=score >= spec.threshold,
        details={
            "score": round(score, 4),
            "reasoning": parsed.get("reasoning", ""),
            "threshold": spec.threshold,
        },
    )


def _parse_judge_response(raw: str) -> dict[str, Any] | None:
    """Pull the JSON object out of a (possibly noisy) LLM response."""
    raw = raw.strip()
    # Try direct parse first
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fall back to scanning for the first {...} block
    match = _JSON_RE.search(raw)
    if match is None:
        return None
    try:
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        return None
    return None


# ---------------------------------------------------------------------------
# Structural (programmatic checks on output + soul state)
# ---------------------------------------------------------------------------


def score_structural(
    case: EvalCase,
    execution: CaseExecution,
    spec: StructuralScoring,
    soul: Soul,
) -> ScoreOutcome:
    """Programmatic checks against the output and the soul's state.

    Each present key in ``spec.expected`` runs as one check. The score
    is fraction-of-checks-passed; the case passes when score >=
    threshold. See :class:`StructuralScoring` for the supported keys.
    """
    expected = spec.expected
    if not expected:
        return ScoreOutcome(
            score=0.0,
            passed=False,
            details={"error": "structural scoring needs at least one expected key"},
        )

    checks: list[tuple[str, bool, Any]] = []  # (key, passed, observed)
    text = execution.output_text
    text_lower = text.lower()

    if "output_contains_bonded_user" in expected:
        want = bool(expected["output_contains_bonded_user"])
        bonded_users: set[str] = set()
        if soul.identity.bonded_to:
            bonded_users.add(soul.identity.bonded_to)
        for bt in soul.identity.bonds:
            if bt.id:
                bonded_users.add(bt.id)
            if bt.label:
                bonded_users.add(bt.label)
        # Per-user bonds count too
        try:
            bonded_users.update(soul.bond.users())
        except AttributeError:
            pass
        hit = any(uid.lower() in text_lower for uid in bonded_users if uid)
        checks.append(("output_contains_bonded_user", hit == want, hit))

    if "output_contains_user_id" in expected:
        wanted_uid = str(expected["output_contains_user_id"])
        hit = wanted_uid.lower() in text_lower
        checks.append(("output_contains_user_id", hit, hit))

    if "mood_after" in expected:
        wanted_mood = expected["mood_after"]
        observed = execution.mood_after
        # Accept either Mood or string
        try:
            wanted_enum = wanted_mood if isinstance(wanted_mood, Mood) else Mood(wanted_mood)
        except ValueError:
            checks.append(("mood_after", False, str(observed)))
        else:
            checks.append(("mood_after", observed == wanted_enum, str(observed)))

    if "min_energy_after" in expected:
        threshold = float(expected["min_energy_after"])
        observed = execution.energy_after
        checks.append(("min_energy_after", observed >= threshold, observed))

    if "max_energy_after" in expected:
        threshold = float(expected["max_energy_after"])
        observed = execution.energy_after
        checks.append(("max_energy_after", observed <= threshold, observed))

    if "recall_min_results" in expected:
        wanted = int(expected["recall_min_results"])
        observed = len(execution.recall_results)
        checks.append(("recall_min_results", observed >= wanted, observed))

    if "recall_expected_substring" in expected:
        sub = str(expected["recall_expected_substring"]).lower()
        hit = any(sub in (m.content or "").lower() for m in execution.recall_results)
        checks.append(("recall_expected_substring", hit, hit))

    if not checks:
        return ScoreOutcome(
            score=0.0,
            passed=False,
            details={
                "error": "no recognized structural keys in expected",
                "supported": [
                    "output_contains_bonded_user",
                    "output_contains_user_id",
                    "mood_after",
                    "min_energy_after",
                    "max_energy_after",
                    "recall_min_results",
                    "recall_expected_substring",
                ],
                "got": list(expected.keys()),
            },
        )

    passed_count = sum(1 for _, ok, _ in checks if ok)
    score = passed_count / len(checks)
    return ScoreOutcome(
        score=score,
        passed=score >= spec.threshold,
        details={
            "checks": [{"key": k, "passed": ok, "observed": obs} for k, ok, obs in checks],
            "passed_count": passed_count,
            "total_count": len(checks),
            "threshold": spec.threshold,
        },
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def score_case(
    case: EvalCase,
    execution: CaseExecution,
    soul: Soul,
    engine: CognitiveEngine | None,
) -> ScoreOutcome:
    """Dispatch to the right scorer based on ``case.scoring.kind``."""
    scoring = case.scoring
    if isinstance(scoring, KeywordScoring):
        return score_keyword(case, execution, scoring)
    if isinstance(scoring, RegexScoring):
        return score_regex(case, execution, scoring)
    if isinstance(scoring, SemanticScoring):
        return score_semantic(case, execution, scoring)
    if isinstance(scoring, JudgeScoring):
        return await score_judge(case, execution, scoring, engine)
    if isinstance(scoring, StructuralScoring):
        return score_structural(case, execution, scoring, soul)
    # Should be unreachable because Scoring is a discriminated union
    return ScoreOutcome(
        score=0.0,
        passed=False,
        details={"error": f"unknown scoring kind: {type(scoring).__name__}"},
    )
