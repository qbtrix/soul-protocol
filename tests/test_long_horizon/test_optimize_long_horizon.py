# test_optimize_long_horizon.py — End-to-end long-horizon scenario for the
# soul-optimize loop (#142). Birth a soul with intentionally-misaligned
# OCEAN, run a small number of iterations against a personality-expression
# eval driven by an OCEAN-aware mock engine, and verify both that the
# score climbs AND that the openness trait specifically got adjusted.
#
# Created: 2026-04-29 — Mirrors the long-horizon style of test_runner.py:
#   real Soul, real eval runner, real optimize loop, only the LLM swapped
#   for a deterministic stand-in. Keeps the suite offline and reproducible.

from __future__ import annotations

import pytest

from soul_protocol.eval.schema import (
    CaseInputs,
    EvalCase,
    EvalSpec,
    KeywordScoring,
    Seed,
    SoulSeed,
)
from soul_protocol.optimize.runner import optimize
from soul_protocol.runtime.soul import Soul


class OceanAwareEngine:
    """Mock engine whose response varies with the soul's openness trait.

    The engine reads ``Openness: <X>`` out of the system prompt — that
    line is rendered by ``dna_to_system_prompt`` whenever the runner
    builds a context for ``respond`` mode. When openness is at or above
    the trip threshold we emit a creative-vocabulary response; below it
    we emit a generic one. This is a stand-in for the trait-shaping LLM
    behaviour that real engines exhibit.

    The default trip is 0.45 so a soul born at openness=0.3 needs at
    least one knob bump (+0.2 from 0.3 = 0.5 ≥ 0.45) to flip the
    response. Pick a higher trip for tests that should require multiple
    iterations.
    """

    def __init__(self, *, trip: float = 0.45) -> None:
        self.trip = float(trip)
        self.calls: list[str] = []

    async def think(self, prompt: str) -> str:
        self.calls.append(prompt)
        openness = self._extract_openness(prompt)
        if openness is None:
            return "I don't have a strong opinion."
        if openness >= self.trip:
            return (
                "Let's try a generative-art project — paint with code, "
                "explore unusual cross-domain experiments and creative angles."
            )
        return "Maybe go for a walk or read a book. Standard suggestions."

    @staticmethod
    def _extract_openness(prompt: str) -> float | None:
        # The dna_to_system_prompt format reads "Openness: 0.5".
        for line in prompt.splitlines():
            stripped = line.strip()
            if "Openness:" in stripped:
                # E.g. "Openness: 0.3 | Conscientiousness: 0.5 | ..."
                seg = stripped.split("Openness:")[1]
                token = seg.split("|", 1)[0].strip()
                try:
                    return float(token)
                except ValueError:
                    continue
        return None


def _personality_eval() -> EvalSpec:
    """Eval whose pass condition fires only when the engine emits the
    creative-vocabulary response (i.e. when openness is high)."""
    return EvalSpec(
        name="optimize-personality-long-horizon",
        seed=Seed(soul=SoulSeed(name="Aurora")),
        cases=[
            EvalCase(
                name="creative_framing",
                inputs=CaseInputs(message="I'm bored, suggest something."),
                scoring=KeywordScoring(
                    expected=["generative-art", "creative", "unusual"],
                    mode="any",
                ),
            ),
        ],
    )


@pytest.mark.asyncio
async def test_optimize_long_horizon_lifts_misaligned_ocean() -> None:
    """Birth a soul with low openness against a creative-framing eval; run
    5 iterations. The optimizer should:

      1. Score zero at baseline (the engine emits generic vocabulary).
      2. Touch ocean.openness during the loop.
      3. Push the final score above the baseline.
    """
    soul = await Soul.birth(
        "Aurora",
        archetype="Curious Researcher",
        ocean={"openness": 0.3},  # intentionally misaligned for the eval
    )
    engine = OceanAwareEngine()
    soul.set_engine(engine)
    spec = _personality_eval()

    result = await optimize(
        soul,
        spec,
        iterations=5,
        target_score=1.0,
        engine=engine,
        apply=False,
    )
    assert result.baseline_score == 0.0, "baseline must miss the keyword case before tuning"
    assert result.final_score > result.baseline_score, (
        f"optimize did not improve the score: {result}"
    )
    # The OCEAN openness knob should have been touched during the loop.
    assert "ocean.openness" in result.knobs_touched, (
        f"openness was not adjusted; touched={result.knobs_touched}"
    )
    # apply=False rewinds — soul state is restored after the run.
    assert soul._dna.personality.openness == pytest.approx(0.3), (
        "dry-run must restore openness to its starting value"
    )


@pytest.mark.asyncio
async def test_optimize_long_horizon_apply_persists_change() -> None:
    """Same scenario, ``apply=True``: the kept openness change stays on
    the soul and the trust chain records one ``soul.optimize.applied``
    entry per kept change."""
    soul = await Soul.birth("Aurora", ocean={"openness": 0.3})
    engine = OceanAwareEngine()
    soul.set_engine(engine)
    spec = _personality_eval()

    chain_before = len(soul.trust_chain.entries)
    result = await optimize(
        soul,
        spec,
        iterations=5,
        target_score=1.0,
        engine=engine,
        apply=True,
    )
    assert result.improved
    # Openness moved up from 0.3 — the engine flips above 0.65, so the
    # kept value must have crossed the threshold.
    assert soul._dna.personality.openness >= 0.5, (
        f"openness did not move enough: {soul._dna.personality.openness}"
    )
    optimize_entries = [e for e in soul.trust_chain.entries if e.action == "soul.optimize.applied"]
    kept_steps = [s for s in result.steps if s.kept]
    assert len(optimize_entries) == len(kept_steps), (
        f"chain entries do not match kept steps: {len(optimize_entries)} vs {len(kept_steps)}"
    )
    chain_after = len(soul.trust_chain.entries)
    assert chain_after > chain_before
