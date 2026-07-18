# eval/runner.py — Eval runner for soul-aware evaluations.
# Created: 2026-04-29 (#160) — Births a soul from the EvalSpec seed, applies
#   memories / bonds / state, then iterates cases. For each case the runner
#   either drives the soul into producing a response (mode="respond") or
#   calls Soul.recall() (mode="recall"), captures state snapshots, and
#   delegates to the scoring module.
#
# The "respond" path is the interesting one. soul-protocol does not own a
# response generator — that's the consumer's job — so the runner builds the
# same context an agent would build (system prompt + per-turn context block)
# and asks the configured engine for a reply. When no engine is configured
# we fall back to a deterministic synthesis that surfaces the soul's state
# and recalled memories so keyword / structural cases still produce
# meaningful output.

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType

from .schema import (
    EvalCase,
    EvalSpec,
    MemorySeed,
    Seed,
    StateSeed,
    load_eval_spec,
)
from .scoring import CaseExecution, ScoreOutcome, score_case

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class CaseResult(BaseModel):
    """Result of running one case."""

    name: str
    passed: bool
    score: float
    skipped: bool = False
    duration_ms: int = 0
    output: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @property
    def status(self) -> str:
        """``"pass" | "fail" | "skip" | "error"`` for display."""
        if self.error:
            return "error"
        if self.skipped:
            return "skip"
        return "pass" if self.passed else "fail"


class EvalResult(BaseModel):
    """Aggregated result of an :class:`EvalSpec` run."""

    spec_name: str
    cases: list[CaseResult] = Field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None  # set when seed application failed

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.cases if c.passed and not c.skipped)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.cases if not c.passed and not c.skipped and not c.error)

    @property
    def skip_count(self) -> int:
        return sum(1 for c in self.cases if c.skipped)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.cases if c.error)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def all_passed(self) -> bool:
        """True when every case either passed or was skipped (no failures, no errors)."""
        return self.fail_count == 0 and self.error_count == 0 and self.error is None


# ---------------------------------------------------------------------------
# Seed application
# ---------------------------------------------------------------------------


async def _birth_soul(seed: Seed, engine: CognitiveEngine | None) -> Soul:
    """Birth a soul from the seed (in-memory only, no .soul file)."""
    soul_seed = seed.soul
    ocean = soul_seed.ocean.model_dump()
    soul = await Soul.birth(
        name=soul_seed.name,
        archetype=soul_seed.archetype,
        personality=soul_seed.persona,
        values=list(soul_seed.values),
        bonded_to=soul_seed.bonded_to,
        ocean=ocean,
        engine=engine,
    )
    return soul


def _apply_state(soul: Soul, state: StateSeed) -> None:
    """Override soul state from the seed.

    Energy and social_battery in :class:`StateSeed` are absolute targets
    (0-100). ``Soul.feel(energy=...)`` treats numbers as deltas, so we
    set the :class:`SoulState` Pydantic fields directly via the public
    :attr:`Soul.state` accessor.
    """
    current = soul.state
    if state.mood is not None:
        current.mood = state.mood
    if state.energy is not None:
        current.energy = float(state.energy)
    if state.social_battery is not None:
        current.social_battery = float(state.social_battery)
    if state.focus is not None:
        # focus accepts a level name or "auto" — go through feel() so
        # focus_override semantics match the rest of the runtime.
        soul.feel(focus=state.focus)


async def _apply_memories(soul: Soul, memories: list[MemorySeed]) -> None:
    """Install seeded memories into the soul.

    We call ``soul.remember`` with the right ``type`` enum when the seed's
    ``layer`` matches a known :class:`MemoryType`; otherwise we drop a
    raw :class:`MemoryEntry` directly through the memory manager so
    user-defined layers round-trip cleanly.
    """
    for mem in memories:
        layer = mem.layer.lower()
        try:
            mtype = MemoryType(layer)
        except ValueError:
            mtype = None
        if mtype is not None:
            await soul.remember(
                content=mem.content,
                type=mtype,
                importance=mem.importance,
                emotion=mem.emotion,
                entities=mem.entities,
                domain=mem.domain,
                user_id=mem.user_id,
            )
        else:
            # Custom layer — bypass the type-keyed remember and drop a
            # raw MemoryEntry through the layer-aware dispatcher so the
            # custom layer string actually routes to the user-defined
            # store rather than the type-keyed default.
            entry = MemoryEntry(
                # MemoryType is required by the model; pick semantic as a
                # neutral default for custom-layer entries.
                type=MemoryType.SEMANTIC,
                content=mem.content,
                importance=mem.importance,
                emotion=mem.emotion,
                entities=list(mem.entities),
                domain=mem.domain,
                user_id=mem.user_id,
                layer=layer,
            )
            await soul._memory._store_in_layer(layer, entry)


def _apply_bonds(soul: Soul, bond_strength: dict[str, float]) -> None:
    """Set per-user bond strengths on the registry."""
    for user_id, strength in bond_strength.items():
        bond = soul.bond.for_user(user_id)
        bond.bond_strength = float(strength)


# ---------------------------------------------------------------------------
# Case execution
# ---------------------------------------------------------------------------


_FALLBACK_PREFIX = "[soul-eval fallback response]"


async def _run_case(
    soul: Soul,
    case: EvalCase,
    engine: CognitiveEngine | None,
) -> CaseExecution:
    """Drive the soul through one case and capture the result."""
    inputs = case.inputs
    mood_before = soul.state.mood
    energy_before = soul.state.energy

    if inputs.mode == "recall":
        layer = inputs.recall_layer
        mtypes: list[MemoryType] | None = None
        if layer:
            try:
                mtypes = [MemoryType(layer.lower())]
            except ValueError:
                # Custom layer — pass via layer kwarg instead
                mtypes = None
        results = await soul.recall(
            query=inputs.message,
            limit=inputs.recall_limit,
            user_id=inputs.user_id,
            domain=inputs.domain,
            layer=layer if mtypes is None else None,
            types=mtypes,
        )
        # Render recall results as plain text so keyword/semantic/regex
        # scorers see a single string. Structural scoring reads
        # ``recall_results`` directly.
        rendered = "\n".join(f"- {m.content}" for m in results)
        execution = CaseExecution(
            output_text=rendered,
            recall_results=list(results),
            mood_before=mood_before,
            energy_before=energy_before,
        )
    else:  # "respond"
        output = await _produce_response(soul, inputs.message, inputs.user_id, engine)
        execution = CaseExecution(
            output_text=output,
            mood_before=mood_before,
            energy_before=energy_before,
        )
        if inputs.observe:
            interaction = Interaction.from_pair(
                user_input=inputs.message,
                agent_output=output,
                channel="eval",
            )
            await soul.observe(
                interaction,
                user_id=inputs.user_id,
                domain=inputs.domain or "default",
            )

    execution.mood_after = soul.state.mood
    execution.energy_after = soul.state.energy
    return execution


async def _produce_response(
    soul: Soul,
    message: str,
    user_id: str | None,
    engine: CognitiveEngine | None,
) -> str:
    """Produce a soul response to ``message``.

    With an engine configured: build the same context an agent would
    (system prompt + per-turn context block) and ask the engine for a
    reply. Without an engine: synthesize a deterministic fallback that
    surfaces state + recalled memories. The fallback is good enough for
    keyword / semantic / structural scoring; judge cases skip cleanly.
    """
    context = await soul.context_for(message, max_memories=5, include_self_model=True)
    if engine is None:
        return _fallback_response(soul, message, context)

    system_prompt = soul.to_system_prompt(safety_guardrails=False)
    prompt = (
        f"{system_prompt}\n\n"
        f"{context}"
        f"User message: {message}\n\n"
        f"Respond as the soul would, in one or two paragraphs."
    )
    try:
        return (await engine.think(prompt)).strip()
    except Exception as e:  # pragma: no cover — engine errors are infra
        logger.warning("engine.think failed during eval: %s", e)
        return _fallback_response(soul, message, context)


def _fallback_response(soul: Soul, message: str, context: str) -> str:
    """Deterministic stand-in when no engine is wired.

    Surfaces enough of the soul (name, mood, recalled memories) for
    keyword / semantic / structural scoring to do meaningful work.
    """
    parts = [
        f"{_FALLBACK_PREFIX} {soul.name} ({soul.state.mood.value})",
        context.strip(),
        f"To: {message}",
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------


async def run_eval(
    spec: EvalSpec,
    *,
    engine: CognitiveEngine | None = None,
    case_filter: str | None = None,
) -> EvalResult:
    """Run an :class:`EvalSpec` and return aggregated results.

    Args:
        spec: The validated eval spec.
        engine: Optional :class:`CognitiveEngine` for response generation
            and judge scoring. When ``None`` the runner synthesizes
            deterministic fallback responses and skips judge cases.
        case_filter: Optional substring filter — only cases whose
            ``name`` contains this substring run. The rest are silently
            skipped (not recorded in the result).

    Returns:
        :class:`EvalResult` with per-case outcomes.
    """
    started = time.monotonic()
    result = EvalResult(spec_name=spec.name)

    try:
        soul = await _birth_soul(spec.seed, engine)
        _apply_state(soul, spec.seed.state)
        _apply_bonds(soul, spec.seed.bond_strength)
        await _apply_memories(soul, spec.seed.memories)
    except Exception as e:
        logger.exception("seed application failed for spec %s", spec.name)
        result.error = f"seed application failed: {e}"
        result.duration_ms = int((time.monotonic() - started) * 1000)
        return result

    cases = list(spec.cases)
    if case_filter:
        cases = [c for c in cases if case_filter in c.name]

    for case in cases:
        case_started = time.monotonic()
        try:
            execution = await _run_case(soul, case, engine)
            outcome: ScoreOutcome = await score_case(case, execution, soul, engine)
            result.cases.append(
                CaseResult(
                    name=case.name,
                    passed=outcome.passed,
                    score=outcome.score,
                    skipped=outcome.skipped,
                    duration_ms=int((time.monotonic() - case_started) * 1000),
                    output=execution.output_text[:1000],  # truncate for the report
                    details=outcome.details,
                )
            )
        except Exception as e:
            logger.exception("case %s raised", case.name)
            result.cases.append(
                CaseResult(
                    name=case.name,
                    passed=False,
                    score=0.0,
                    duration_ms=int((time.monotonic() - case_started) * 1000),
                    error=f"{type(e).__name__}: {e}",
                )
            )

    result.duration_ms = int((time.monotonic() - started) * 1000)
    return result


async def run_eval_file(
    path: str | Path,
    *,
    engine: CognitiveEngine | None = None,
    case_filter: str | None = None,
) -> EvalResult:
    """Convenience wrapper: load a YAML spec and run it."""
    spec = load_eval_spec(path)
    return await run_eval(spec, engine=engine, case_filter=case_filter)


async def run_eval_against_soul(
    spec: EvalSpec,
    soul: Soul,
    *,
    engine: CognitiveEngine | None = None,
    case_filter: str | None = None,
) -> EvalResult:
    """Run an eval against an existing soul without re-birthing.

    Used by the MCP ``soul_eval`` tool so an agent can self-evaluate
    against its current state. The seed block on the spec is ignored —
    only ``cases`` are executed. State / memories on the soul are read
    as-is.

    Args:
        spec: The validated eval spec. ``spec.seed`` is intentionally
            ignored; the soul's live state is the seed.
        soul: The soul to drive cases against.
        engine: Optional engine for response generation and judge
            scoring. When ``None`` we read ``soul._engine`` and use it
            if present.
        case_filter: Optional substring filter on case names.

    Returns:
        :class:`EvalResult` with per-case outcomes.
    """
    started = time.monotonic()
    result = EvalResult(spec_name=spec.name)

    effective_engine = engine if engine is not None else getattr(soul, "_engine", None)

    cases = list(spec.cases)
    if case_filter:
        cases = [c for c in cases if case_filter in c.name]

    for case in cases:
        case_started = time.monotonic()
        try:
            execution = await _run_case(soul, case, effective_engine)
            outcome: ScoreOutcome = await score_case(case, execution, soul, effective_engine)
            result.cases.append(
                CaseResult(
                    name=case.name,
                    passed=outcome.passed,
                    score=outcome.score,
                    skipped=outcome.skipped,
                    duration_ms=int((time.monotonic() - case_started) * 1000),
                    output=execution.output_text[:1000],
                    details=outcome.details,
                )
            )
        except Exception as e:
            logger.exception("case %s raised", case.name)
            result.cases.append(
                CaseResult(
                    name=case.name,
                    passed=False,
                    score=0.0,
                    duration_ms=int((time.monotonic() - case_started) * 1000),
                    error=f"{type(e).__name__}: {e}",
                )
            )

    result.duration_ms = int((time.monotonic() - started) * 1000)
    return result
