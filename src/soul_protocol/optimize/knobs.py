# optimize/knobs.py — Knob protocol + built-in knobs for the optimize loop.
# Created: 2026-04-29 (#142) — A "knob" is a parameter the optimizer is
#   allowed to adjust on a soul. Each knob exposes current_value() / apply()
#   / revert() / candidates(). Built-ins: OceanTraitKnob (one OCEAN trait,
#   ±0.1/±0.2 within [0,1]), PersonaTextKnob (alternate persona phrasings
#   via the cognitive engine; identity passthrough as heuristic fallback),
#   SignificanceThresholdKnob (MemorySettings.skip_deep_processing_on_low_significance
#   plus the importance threshold ±1), BondThresholdKnob (default
#   bond.bond_strength ±5/±10).
#
# Knobs are pluggable via OptimizeRunner.register_knob; the four shipped
# here are sensible defaults that exercise the four big tuning surfaces
# the brief calls out (OCEAN, persona, memory thresholds, bond).
#
# Important semantics:
#   - apply() and revert() are pure mutations; they DO NOT append trust
#     chain entries. Chain hooks live in the runner so probe attempts that
#     get rolled back never pollute the audit log.
#   - candidates(current) returns adjacent values, ranked by step size.
#     Out-of-range candidates are clamped at construction time so the
#     runner can apply them without a follow-up validation pass.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.soul import Soul


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Knob(Protocol):
    """Pluggable adjustment surface for the optimize loop.

    A knob describes "one thing the optimizer is allowed to change." The
    runner calls :meth:`current_value` to snapshot, :meth:`apply` to set
    a candidate, and :meth:`revert` to roll back if the change didn't
    improve the eval score. :meth:`candidates` proposes adjacent values
    to trial, ranked from smallest to largest perturbation.
    """

    name: str

    async def current_value(self, soul: Soul) -> Any: ...

    async def apply(self, soul: Soul, value: Any) -> None: ...

    async def revert(self, soul: Soul, original: Any) -> None: ...

    def candidates(self, current: Any) -> list[Any]: ...


# ---------------------------------------------------------------------------
# OCEAN trait knob
# ---------------------------------------------------------------------------


_OCEAN_TRAITS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)


class OceanTraitKnob:
    """Adjust one OCEAN personality trait on the soul's :class:`Personality`.

    Candidate values are ±0.1, ±0.2 around the current value, clamped to
    [0.0, 1.0]. Apply mutates ``soul._dna.personality`` directly so the
    change is immediately observable to the eval runner; revert restores
    the original. The runner is responsible for trust-chain bookkeeping
    when a change is kept.
    """

    def __init__(self, trait: str, *, step_sizes: tuple[float, ...] = (0.1, 0.2)) -> None:
        if trait not in _OCEAN_TRAITS:
            raise ValueError(
                f"Unknown OCEAN trait {trait!r}; must be one of {', '.join(_OCEAN_TRAITS)}",
            )
        self.trait: str = trait
        self.name: str = f"ocean.{trait}"
        self._step_sizes: tuple[float, ...] = tuple(step_sizes)

    async def current_value(self, soul: Soul) -> float:
        return float(getattr(soul._dna.personality, self.trait))

    async def apply(self, soul: Soul, value: Any) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        setattr(soul._dna.personality, self.trait, clamped)

    async def revert(self, soul: Soul, original: Any) -> None:
        await self.apply(soul, original)

    def candidates(self, current: Any) -> list[float]:
        cur = float(current)
        out: list[float] = []
        seen: set[float] = set()
        # Walk step sizes in order: each step contributes "+step then -step".
        # That way the smaller perturbation goes first regardless of sign.
        for step in self._step_sizes:
            for delta in (step, -step):
                v = round(max(0.0, min(1.0, cur + delta)), 4)
                if v != cur and v not in seen:
                    out.append(v)
                    seen.add(v)
        return out


# ---------------------------------------------------------------------------
# Persona text knob
# ---------------------------------------------------------------------------


_PERSONA_REPHRASE_PROMPT = (
    "You are helping tune an AI agent's persona text. Below is the current "
    "persona description.\n\n"
    "Current persona:\n{persona}\n\n"
    "Failing eval cases (the persona may be contributing to these failures):\n"
    "{failing_cases}\n\n"
    "Propose ONE alternate phrasing of the persona that addresses the failing "
    "cases without contradicting the soul's existing values. Keep the same "
    "approximate length. Return ONLY the new persona text — no preamble, no "
    "quotes, no explanation."
)


class PersonaTextKnob:
    """Propose alternate persona phrasings via the cognitive engine.

    With a wired :class:`CognitiveEngine`, :meth:`candidates` returns one
    or more LLM-generated rephrasings tailored to the failing cases.
    Without an engine the knob is effectively a no-op — :meth:`candidates`
    returns ``[]`` and the runner skips it.

    Apply replaces ``soul.get_core_memory().persona`` outright. Revert
    restores the original. The persona text is never appended to — each
    apply is a full replacement.
    """

    name: str = "core.persona"

    def __init__(
        self,
        engine: CognitiveEngine | None = None,
        failing_cases: list[str] | None = None,
        candidates_override: list[str] | None = None,
    ) -> None:
        self._engine = engine
        self._failing_cases: list[str] = list(failing_cases or [])
        # Tests + heuristic fallback can pre-seed candidates without an LLM.
        self._candidates_override: list[str] | None = (
            list(candidates_override) if candidates_override is not None else None
        )

    def set_failing_cases(self, cases: list[str]) -> None:
        """Update the failing-cases list used in the LLM prompt.

        Called by the runner / proposer so the persona suggestion is
        grounded in the eval failures from the most recent iteration.
        """
        self._failing_cases = list(cases)

    def set_engine(self, engine: CognitiveEngine | None) -> None:
        self._engine = engine

    async def current_value(self, soul: Soul) -> str:
        return soul.get_core_memory().persona

    async def apply(self, soul: Soul, value: Any) -> None:
        # Use the underlying memory manager so the call is a REPLACE, not
        # an append. ``Soul.edit_core_memory`` also replaces today, but
        # going through the manager keeps the contract explicit.
        soul._memory.set_core(
            persona=str(value),
            human=soul.get_core_memory().human,
        )

    async def revert(self, soul: Soul, original: Any) -> None:
        await self.apply(soul, original)

    def candidates(self, current: Any) -> list[str]:
        # Heuristic / test path
        if self._candidates_override is not None:
            return [c for c in self._candidates_override if c != current]
        # Engine path is async; surfaced via :meth:`async_candidates`.
        return []

    async def async_candidates(self, current: Any) -> list[str]:
        """LLM-driven candidate generation.

        Falls back to ``[]`` (the heuristic no-op) when no engine is wired
        or the engine raises. Caller is the proposer, not the runner — the
        sync :meth:`candidates` covers the override / heuristic path so
        registration code that doesn't know about the LLM can still walk
        the knob.
        """
        if self._candidates_override is not None:
            return [c for c in self._candidates_override if c != current]
        if self._engine is None:
            return []
        prompt = _PERSONA_REPHRASE_PROMPT.format(
            persona=str(current).strip() or "(no persona text set)",
            failing_cases=(
                "\n".join(f"- {c}" for c in self._failing_cases)
                if self._failing_cases
                else "(no specific failing cases reported)"
            ),
        )
        try:
            raw = await self._engine.think(prompt)
        except Exception:
            return []
        candidate = (raw or "").strip()
        # Strip surrounding quotes if the engine added them.
        if len(candidate) >= 2 and candidate[0] in {'"', "'"} and candidate[-1] == candidate[0]:
            candidate = candidate[1:-1].strip()
        if not candidate or candidate == current:
            return []
        return [candidate]


# ---------------------------------------------------------------------------
# Significance threshold knob — affects observe() short-circuit + importance gate
# ---------------------------------------------------------------------------


class SignificanceThresholdKnob:
    """Adjust the soul's significance / importance gates for memory write.

    Backed by two fields on :class:`MemorySettings`:

    - ``importance_threshold`` (int, 1-10): minimum importance for a fact
      to enter semantic memory. The knob trials ±1 around the current.
    - ``skip_deep_processing_on_low_significance`` (bool): when True the
      observe() pipeline short-circuits self-model updates for low-sig
      interactions. The knob trials the opposite of the current bool.

    A "value" for this knob is the tuple ``(threshold, skip_deep)`` —
    apply/revert set both at once. The default :meth:`candidates` walks
    threshold first, then the bool flip.
    """

    name: str = "memory.significance"

    def __init__(
        self,
        *,
        threshold_step: int = 1,
        threshold_bounds: tuple[int, int] = (1, 10),
    ) -> None:
        self._threshold_step = max(1, int(threshold_step))
        self._threshold_lo, self._threshold_hi = threshold_bounds

    async def current_value(self, soul: Soul) -> tuple[int, bool]:
        s = soul._memory.settings
        return (int(s.importance_threshold), bool(s.skip_deep_processing_on_low_significance))

    async def apply(self, soul: Soul, value: Any) -> None:
        threshold, skip_deep = self._unpack(value)
        s = soul._memory.settings
        s.importance_threshold = int(max(self._threshold_lo, min(self._threshold_hi, threshold)))
        s.skip_deep_processing_on_low_significance = bool(skip_deep)

    async def revert(self, soul: Soul, original: Any) -> None:
        await self.apply(soul, original)

    def candidates(self, current: Any) -> list[tuple[int, bool]]:
        threshold, skip_deep = self._unpack(current)
        out: list[tuple[int, bool]] = []
        seen: set[tuple[int, bool]] = set()
        # Walk threshold ±step first; smaller perturbation surfaces first.
        for delta in (self._threshold_step, -self._threshold_step):
            v = max(self._threshold_lo, min(self._threshold_hi, threshold + delta))
            cand = (int(v), skip_deep)
            if cand != (threshold, skip_deep) and cand not in seen:
                out.append(cand)
                seen.add(cand)
        # Bool flip last — bigger qualitative change.
        flip = (threshold, not skip_deep)
        if flip not in seen:
            out.append(flip)
            seen.add(flip)
        return out

    @staticmethod
    def _unpack(value: Any) -> tuple[int, bool]:
        # Accept tuple/list/dict for ergonomic test wiring.
        if isinstance(value, dict):
            return (int(value["threshold"]), bool(value["skip_deep"]))
        if isinstance(value, list | tuple) and len(value) == 2:
            return (int(value[0]), bool(value[1]))
        raise TypeError(
            f"SignificanceThresholdKnob value must be (threshold, skip_deep), got {value!r}"
        )


# ---------------------------------------------------------------------------
# Bond threshold knob — adjusts default bond.bond_strength
# ---------------------------------------------------------------------------


class BondThresholdKnob:
    """Adjust the soul's default bond strength to gate BONDED memory recall.

    soul-protocol gates memories tagged ``MemoryVisibility.BONDED`` behind
    ``bond_strength >= bond_threshold``. The eval runner does not pass an
    explicit ``bond_strength`` per case, so the soul's default
    ``bond.bond_strength`` is what governs visibility for the soul itself
    when it recalls. Raising it surfaces more memory; lowering it tightens
    privacy.

    Direct attribute mutation here intentionally bypasses the
    ``BondRegistry`` ``on_change`` callback — that callback writes
    ``bond.strengthen`` / ``bond.weaken`` chain entries, and we want
    probe-and-revert experiments to be silent. The runner emits its own
    ``soul.optimize.applied`` chain entries when changes are kept.
    """

    name: str = "bond.default_strength"

    def __init__(
        self,
        *,
        step_sizes: tuple[float, ...] = (5.0, 10.0),
        bounds: tuple[float, float] = (0.0, 100.0),
    ) -> None:
        self._step_sizes: tuple[float, ...] = tuple(step_sizes)
        self._lo, self._hi = bounds

    async def current_value(self, soul: Soul) -> float:
        return float(soul.bond.bond_strength)

    async def apply(self, soul: Soul, value: Any) -> None:
        clamped = max(self._lo, min(self._hi, float(value)))
        # Direct mutation of the default Bond bypasses the on_change hook.
        # See class docstring for rationale.
        soul.bond._default.bond_strength = clamped

    async def revert(self, soul: Soul, original: Any) -> None:
        await self.apply(soul, original)

    def candidates(self, current: Any) -> list[float]:
        cur = float(current)
        out: list[float] = []
        seen: set[float] = set()
        for step in self._step_sizes:
            for delta in (step, -step):
                v = round(max(self._lo, min(self._hi, cur + delta)), 4)
                if v != cur and v not in seen:
                    out.append(v)
                    seen.add(v)
        return out


# ---------------------------------------------------------------------------
# Default knob set
# ---------------------------------------------------------------------------


def default_knobs(*, engine: CognitiveEngine | None = None) -> list[Knob]:
    """Return the standard knob set for an optimize run.

    Includes one :class:`OceanTraitKnob` per OCEAN dimension, the persona
    knob (LLM-aware when ``engine`` is provided), the significance
    threshold knob, and the bond threshold knob. Callers that want a
    smaller / different surface can build their own list and pass it to
    :func:`optimize` directly.
    """
    knobs: list[Knob] = [OceanTraitKnob(t) for t in _OCEAN_TRAITS]
    knobs.append(PersonaTextKnob(engine=engine))
    knobs.append(SignificanceThresholdKnob())
    knobs.append(BondThresholdKnob())
    return knobs


__all__ = [
    "Knob",
    "OceanTraitKnob",
    "PersonaTextKnob",
    "SignificanceThresholdKnob",
    "BondThresholdKnob",
    "default_knobs",
]
