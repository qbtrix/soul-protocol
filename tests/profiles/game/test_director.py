# test_director.py — Deterministic tests for the Pulse director (director.py).
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Eight tests, all
#   pure and synchronous (no Soul, no LLM, no network, no randomness), proving
#   the L4D pacing contract:
#     * test_scripted_arc_builds_to_peak_at_threshold — a scripted beat
#       sequence accrues intensity through BUILD_UP and tips into PEAK exactly
#       when the threshold is crossed (hand-computed heat math).
#     * test_peak_exits_after_peak_beats — PEAK reports itself for exactly
#       peak_beats beats, then hands over to FADE.
#     * test_relax_blocks_escalation_even_under_max_heat — RELAX lasts
#       relax_beats and should_escalate() is False throughout, even when every
#       relax beat is a max-heat betrayal on a GRUDGING relationship; the
#       governor also stays False back in BUILD_UP while intensity remains at
#       or over the ceiling.
#     * test_decay_lowers_intensity_across_quiet_beats — quiet (neutral) beats
#       strictly cool a hot player at the configured decay factor.
#     * test_yes_and_never_vetoes_any_kind — property-style loop over every
#       SEVERITY kind plus unknown/empty kinds: always a non-empty build-on
#       suggestion, never a veto word.
#     * test_enjoyment_signal_scales_peak_threshold — a bored player (0.0)
#       peaks in fewer beats than a delighted one (1.0) under identical beats.
#     * test_pacing_strings_map_to_phases — the four phases speak exactly
#       escalate/sustain/release/rest.
#     * test_intensity_is_per_player — heat lands only on the observed player.
#
# Run:  uv run pytest tests/profiles/game/test_director.py -v

from __future__ import annotations

import pytest

from soul_protocol.profiles.game import GRUDGING, NONE, SLIGHTED
from soul_protocol.profiles.game.director import (
    BUILD_UP,
    FADE,
    PACING_BY_PHASE,
    PEAK,
    PHASES,
    RELAX,
    DirectorEngine,
)
from soul_protocol.profiles.game.grudge import SEVERITY

RAGNAR = "did:soul:player:ragnar"
ASTRID = "did:soul:player:astrid"


def test_scripted_arc_builds_to_peak_at_threshold() -> None:
    """A scripted arc drives BUILD_UP -> PEAK exactly at the threshold.

    decay=1.0 keeps the math additive: 0.05 (neutral) + 0.4 (insult, NONE)
    + 0.84 (theft, SLIGHTED x1.2) = 1.29 < 2.0, still building; the betrayal
    on a GRUDGING relationship (+0.9 x 1.5 = 1.35) crosses 2.0 -> PEAK.
    """
    director = DirectorEngine(peak_threshold=2.0, decay=1.0, peak_beats=3)

    director.observe_beat(RAGNAR, "neutral", NONE)
    assert director.phase == BUILD_UP
    director.observe_beat(RAGNAR, "insult", NONE)
    assert director.phase == BUILD_UP
    director.observe_beat(RAGNAR, "theft", SLIGHTED)
    assert director.phase == BUILD_UP
    assert director.intensity(RAGNAR) == pytest.approx(1.29)
    assert director.should_escalate(RAGNAR)  # below threshold, still building

    director.observe_beat(RAGNAR, "betrayal", GRUDGING)
    assert director.intensity(RAGNAR) == pytest.approx(2.64)
    assert director.phase == PEAK
    assert not director.should_escalate(RAGNAR)  # the governor closed


def test_peak_exits_after_peak_beats() -> None:
    """PEAK reports itself for exactly peak_beats beats, then FADE."""
    director = DirectorEngine(peak_threshold=1.0, decay=1.0, peak_beats=3, fade_beats=2)

    director.observe_beat(RAGNAR, "betrayal", GRUDGING)  # 1.35 >= 1.0 -> PEAK
    phases = [director.phase]
    for _ in range(3):
        director.observe_beat(RAGNAR, "neutral", NONE)
        phases.append(director.phase)

    assert phases == [PEAK, PEAK, PEAK, FADE]
    assert phases.count(PEAK) == director.peak_beats


def test_relax_blocks_escalation_even_under_max_heat() -> None:
    """RELAX is the mandatory quiet window: relax_beats beats where
    should_escalate() is False no matter how hot the beats run."""
    director = DirectorEngine(
        peak_threshold=1.0, decay=1.0, peak_beats=1, fade_beats=1, relax_beats=3
    )
    director.observe_beat(RAGNAR, "betrayal", GRUDGING)  # -> PEAK
    assert director.phase == PEAK
    director.observe_beat(RAGNAR, "betrayal", GRUDGING)  # peak spent -> FADE
    assert director.phase == FADE
    director.observe_beat(RAGNAR, "betrayal", GRUDGING)  # fade spent -> RELAX
    assert director.phase == RELAX

    # Two more MAX-heat beats inside the window: still RELAX, still no green light.
    for _ in range(2):
        assert not director.should_escalate(RAGNAR)
        director.observe_beat(RAGNAR, "betrayal", GRUDGING)
        assert director.phase == RELAX
        assert not director.should_escalate(RAGNAR)

    # The window closes only after relax_beats beats -> a fresh BUILD_UP...
    director.observe_beat(RAGNAR, "betrayal", GRUDGING)
    assert director.phase == BUILD_UP
    # ...and even there the governor stays shut while intensity >= threshold.
    assert director.intensity(RAGNAR) > director.peak_threshold
    assert not director.should_escalate(RAGNAR)


def test_decay_lowers_intensity_across_quiet_beats() -> None:
    """Quiet beats cool a hot player: decay=0.5 halves, the neutral floor
    (0.05) trickles in — 0.9 -> 0.5 -> 0.3 -> 0.2, strictly decreasing."""
    director = DirectorEngine(peak_threshold=10.0, decay=0.5)
    director.observe_beat(RAGNAR, "betrayal", NONE)
    assert director.intensity(RAGNAR) == pytest.approx(0.9)

    readings = [director.intensity(RAGNAR)]
    for expected in (0.5, 0.3, 0.2):
        value = director.observe_beat(RAGNAR, "neutral", NONE)
        assert value == pytest.approx(expected)
        readings.append(value)

    assert all(later < earlier for earlier, later in zip(readings, readings[1:]))
    assert director.phase == BUILD_UP  # never peaked; this is pure cooling


def test_yes_and_never_vetoes_any_kind() -> None:
    """Monolith's rule, property-style: EVERY input — every SEVERITY kind and
    any unknown kind — gets a non-empty build-on suggestion, never a veto."""
    director = DirectorEngine()
    vetoes = {"veto", "block", "deny", "refuse", "negate", "no", "stop", "cancel"}

    for kind in [*SEVERITY, "ambush", "gift", "riddle", ""]:
        suggestion = director.yes_and(kind)
        assert isinstance(suggestion, str) and suggestion
        assert suggestion.lower() not in vetoes
        # Deterministic: the same kind always yields the same suggestion.
        assert director.yes_and(kind) == suggestion

    # Spot-check the curated mappings.
    assert director.yes_and("neutral") == "deepen"
    assert director.yes_and("betrayal") == "consequence"


def test_enjoyment_signal_scales_peak_threshold() -> None:
    """The enjoyment hook scales the threshold: bored (0.0) halves it and
    peaks on beat 1; delighted (1.0) raises it 1.5x and peaks on beat 3."""

    def beats_to_peak(director: DirectorEngine) -> int:
        for beat in range(1, 11):
            director.observe_beat(RAGNAR, "betrayal", GRUDGING)  # 1.35 heat per beat
            if director.phase == PEAK:
                return beat
        raise AssertionError("never peaked")

    bored = DirectorEngine(peak_threshold=2.0, decay=1.0, enjoyment_signal=lambda did: 0.0)
    delighted = DirectorEngine(peak_threshold=2.0, decay=1.0, enjoyment_signal=lambda did: 1.0)

    assert beats_to_peak(bored) == 1  # effective threshold 1.0 < 1.35
    assert beats_to_peak(delighted) == 3  # effective threshold 3.0, crossed at 4.05
    # None (the v0 default) sits between the two: effective threshold == 2.0.
    assert beats_to_peak(DirectorEngine(peak_threshold=2.0, decay=1.0)) == 2


def test_pacing_strings_map_to_phases() -> None:
    """One full cycle speaks exactly escalate/sustain/release/rest, phase by
    phase, and PACING_BY_PHASE covers every phase."""
    assert set(PACING_BY_PHASE) == set(PHASES)

    director = DirectorEngine(
        peak_threshold=1.0, decay=1.0, peak_beats=2, fade_beats=2, relax_beats=2
    )
    seen = {director.phase: director.suggest_pacing(RAGNAR)}  # fresh scene: BUILD_UP
    for _ in range(6):
        director.observe_beat(RAGNAR, "betrayal", GRUDGING)
        seen.setdefault(director.phase, director.suggest_pacing(RAGNAR))

    assert seen == {BUILD_UP: "escalate", PEAK: "sustain", FADE: "release", RELAX: "rest"}


def test_intensity_is_per_player() -> None:
    """Heat lands only on the observed player; a bystander stays cold."""
    director = DirectorEngine()
    director.observe_beat(RAGNAR, "insult", NONE)
    director.observe_beat(RAGNAR, "insult", NONE)

    assert director.intensity(RAGNAR) > 0.0
    assert director.intensity(ASTRID) == 0.0
    assert director.phase == BUILD_UP
    assert director.should_escalate(RAGNAR)  # 0.74 is well under the 2.5 default
    assert director.should_escalate(ASTRID)  # a cold player is fair game too
