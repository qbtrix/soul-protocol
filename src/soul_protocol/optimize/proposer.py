# optimize/proposer.py — Turns eval failures into ranked knob proposals.
# Created: 2026-04-29 (#142) — Two implementation paths share one entry
#   point, :meth:`Proposer.propose`:
#
#   1. LLM-assisted (when an engine is wired): summarize failing cases +
#      current knob values into a single prompt, ask the engine to rank
#      knobs by likely impact, parse the JSON response, fall back to the
#      heuristic on parse failure or engine error.
#
#   2. Heuristic (engine=None): walk every knob, take the first candidate
#      from each, rank by knob priority (OCEAN traits first, then persona,
#      then thresholds). The persona knob's heuristic candidate is empty
#      without an engine, so persona proposals are silently skipped.
#
# The ranking order is the order the runner trials the proposals. The
# runner stops at the first kept change per iteration, so getting the
# "obviously useful" knob first matters more than ranking everything.

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .knobs import (
    BondThresholdKnob,
    Knob,
    OceanTraitKnob,
    PersonaTextKnob,
    SignificanceThresholdKnob,
)
from .types import KnobProposal

if TYPE_CHECKING:
    from soul_protocol.eval.runner import EvalResult
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.soul import Soul

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic priority
# ---------------------------------------------------------------------------


def _knob_priority(knob: Knob) -> int:
    """Static rank for the heuristic proposer.

    Lower wins. OCEAN traits are first because they're the most direct
    expression-shaping lever; persona is second (often-best wider lever);
    significance + bond thresholds are last because they tend to produce
    smaller swings on a single case.
    """
    if isinstance(knob, OceanTraitKnob):
        return 10
    if isinstance(knob, PersonaTextKnob):
        return 20
    if isinstance(knob, SignificanceThresholdKnob):
        return 30
    if isinstance(knob, BondThresholdKnob):
        return 40
    return 50  # custom / user-registered knobs sit below the built-ins


def _failing_case_descriptions(eval_result: EvalResult) -> list[str]:
    """One-line summaries of failed / errored cases, capped at 5.

    The cap keeps the LLM prompt small and avoids spamming the persona
    proposer with hundreds of lines. The runner uses these strings both
    in the prompt and as audit-trail context for the proposed change.
    """
    out: list[str] = []
    for case in eval_result.cases:
        if case.passed and not case.error:
            continue
        if case.skipped:
            continue
        status = "ERROR" if case.error else "FAIL"
        detail = case.error or _scoring_detail(case.details)
        out.append(f"[{status}] {case.name} (score={case.score:.2f}) — {detail}")
    return out[:5]


def _scoring_detail(details: dict) -> str:
    """Pull a short reason from a scoring details dict."""
    if not isinstance(details, dict):
        return ""
    for key in ("reasoning", "missing", "expected", "error"):
        v = details.get(key)
        if v:
            return str(v)[:160]
    return ""


# ---------------------------------------------------------------------------
# LLM prompt + response parsing
# ---------------------------------------------------------------------------


_LLM_PROPOSAL_PROMPT = """You are tuning a soul-protocol AI agent to improve its eval score.

Failing eval cases (most-recent run):
{failing_cases}

Current knob values:
{knob_values}

Available knobs you can ask to change:
{knob_names}

Pick up to {limit} knobs whose change is most likely to improve the eval
score. Return JSON ONLY in this shape — no preamble, no commentary:

{{"proposals": [
  {{"knob": "<knob name>", "reason": "<why this would help, one sentence>"}},
  ...
]}}

Rules:
- Knob names MUST match one of the names above exactly.
- Only return knobs from the list. Do not invent names.
- Order matters: the FIRST proposal is tried first.
- If you have no good idea, return an empty proposals array.
"""


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_llm_response(raw: str) -> list[dict]:
    """Pull a list of ``{"knob": ..., "reason": ...}`` dicts from an LLM reply.

    Tolerant to leading / trailing chatter; uses the same "first JSON
    object in the string" approach as the eval judge parser. Returns an
    empty list on any failure rather than raising — the caller falls back
    to the heuristic ranker.
    """
    if not raw:
        return []
    text = raw.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if match is None:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    proposals = data.get("proposals") if isinstance(data, dict) else None
    if not isinstance(proposals, list):
        return []
    cleaned: list[dict] = []
    for p in proposals:
        if not isinstance(p, dict):
            continue
        name = p.get("knob") or p.get("name")
        if not isinstance(name, str):
            continue
        reason = p.get("reason") or p.get("why") or ""
        cleaned.append({"knob": str(name), "reason": str(reason)})
    return cleaned


# ---------------------------------------------------------------------------
# Proposer
# ---------------------------------------------------------------------------


class Proposer:
    """Generate ranked :class:`KnobProposal` lists from eval failures.

    ``propose`` is the single entry point. With an engine wired the
    proposer asks the LLM for an ordering; without one (or when the LLM
    returns nothing usable), the heuristic ranker fires. Both paths
    return the same shape so the runner doesn't care which fired.
    """

    def __init__(self, *, max_proposals: int = 24) -> None:
        # 24 is a comfortable cap — five OCEAN traits × four candidates
        # each (±0.1, ±0.2) = 20, plus a few slots for the persona /
        # significance / bond knobs.
        self.max_proposals = int(max_proposals)

    async def propose(
        self,
        soul: Soul,
        eval_result: EvalResult,
        knobs: list[Knob],
        engine: CognitiveEngine | None = None,
    ) -> list[KnobProposal]:
        """Return the next set of knob proposals to trial.

        Args:
            soul: The soul under optimization. Used to read current knob
                values for the LLM prompt and to bind candidates to.
            eval_result: The most recent eval run. Failing cases drive the
                proposal direction.
            knobs: The full pool of knobs the runner has available.
            engine: Optional :class:`CognitiveEngine` to drive LLM-assisted
                proposals.

        Returns:
            A list of :class:`KnobProposal` in trial order. The runner
            walks this list top-down per iteration.
        """
        failing = _failing_case_descriptions(eval_result)
        # Plumb the failing cases into the persona knob so its LLM prompt
        # is grounded on real eval misses.
        for k in knobs:
            if isinstance(k, PersonaTextKnob):
                k.set_failing_cases(failing)
                if engine is not None:
                    k.set_engine(engine)

        if engine is not None:
            llm_props = await self._propose_via_llm(soul, eval_result, knobs, engine, failing)
            if llm_props:
                # Augment the LLM ranking with heuristic exploration so a
                # single under-shot LLM proposal doesn't strand the loop.
                # Heuristic proposals that duplicate an LLM proposal (same
                # knob + same candidate) are dropped.
                heuristic = await self._propose_heuristic(soul, knobs)
                seen: set[tuple[str, str]] = {(p.knob_name, repr(p.candidate)) for p in llm_props}
                for hp in heuristic:
                    key = (hp.knob_name, repr(hp.candidate))
                    if key in seen:
                        continue
                    llm_props.append(hp)
                    seen.add(key)
                    if len(llm_props) >= self.max_proposals:
                        break
                return llm_props
            # Fall through to heuristic if the LLM returned nothing usable.
        return await self._propose_heuristic(soul, knobs)

    async def _propose_heuristic(
        self,
        soul: Soul,
        knobs: list[Knob],
    ) -> list[KnobProposal]:
        """Static-priority ranking with every candidate per knob.

        For every knob (in priority order), emit one :class:`KnobProposal`
        per ``candidates(current)`` value. The runner walks the list
        top-down and stops at the first kept change, so widening the
        candidate set per iteration is what lets the loop actually
        explore — a single small step from ``ocean.openness=0.3`` may not
        cross a behaviour threshold, but the next candidate (a larger
        step) might.
        """
        proposals: list[KnobProposal] = []
        ranked = sorted(knobs, key=_knob_priority)
        for knob in ranked:
            try:
                current = await knob.current_value(soul)
            except Exception:  # pragma: no cover — defensive
                logger.warning("knob.current_value failed for %s", knob.name)
                continue
            cand_list = knob.candidates(current)
            if not cand_list and isinstance(knob, PersonaTextKnob):
                # Persona's heuristic side returns []; only the LLM path
                # produces candidates. Skip silently.
                continue
            if not cand_list:
                continue
            for cand in cand_list:
                proposals.append(
                    KnobProposal(
                        knob_name=knob.name,
                        candidate=cand,
                        reason=f"heuristic: try {cand!r} for {knob.name}",
                    )
                )
                if len(proposals) >= self.max_proposals:
                    return proposals
        return proposals

    async def _propose_via_llm(
        self,
        soul: Soul,
        eval_result: EvalResult,
        knobs: list[Knob],
        engine: CognitiveEngine,
        failing: list[str],
    ) -> list[KnobProposal]:
        """Build the prompt, parse the response, bind to candidate values.

        The LLM names knobs; the proposer turns each name back into a
        concrete candidate by calling ``knob.candidates(current)[0]`` (or
        ``async_candidates`` for the persona knob). LLM-named knobs that
        don't exist or return no candidate are dropped silently.
        """
        knob_by_name: dict[str, Knob] = {k.name: k for k in knobs}
        knob_values_lines: list[str] = []
        for k in knobs:
            try:
                current = await k.current_value(soul)
            except Exception:  # pragma: no cover — defensive
                continue
            display = repr(current)
            if isinstance(current, str) and len(display) > 120:
                display = display[:117] + "...'"
            knob_values_lines.append(f"- {k.name}: {display}")
        prompt = _LLM_PROPOSAL_PROMPT.format(
            failing_cases="\n".join(failing) if failing else "(no failing cases)",
            knob_values="\n".join(knob_values_lines),
            knob_names="\n".join(f"- {k.name}" for k in knobs),
            limit=self.max_proposals,
        )
        try:
            raw = await engine.think(prompt)
        except Exception as e:
            logger.warning("LLM proposer engine.think failed: %s", e)
            return []
        parsed = _parse_llm_response(raw)
        proposals: list[KnobProposal] = []
        for item in parsed:
            knob = knob_by_name.get(item["knob"])
            if knob is None:
                continue
            try:
                current = await knob.current_value(soul)
            except Exception:  # pragma: no cover — defensive
                continue
            # Persona knob is the only one whose candidates are async.
            if isinstance(knob, PersonaTextKnob):
                cand_list = await knob.async_candidates(current)
            else:
                cand_list = knob.candidates(current)
            if not cand_list:
                continue
            proposals.append(
                KnobProposal(
                    knob_name=knob.name,
                    candidate=cand_list[0],
                    reason=item.get("reason", ""),
                )
            )
            if len(proposals) >= self.max_proposals:
                break
        return proposals


__all__ = ["Proposer", "KnobProposal"]
