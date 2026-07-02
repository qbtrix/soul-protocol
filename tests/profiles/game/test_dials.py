# test_dials.py — Deterministic tests for the four fun dials (dials.py).
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Eight tests, all
#   pure and synchronous (no Soul, no LLM, no network, no randomness), proving
#   each dial's evidence rule:
#     * test_progress_advances_on_failed_beat — THE evidence rule: a failed
#       beat still advances at least one track (grit + story), at every dial
#       level including 0.0, and the advancement scales with the level.
#     * test_progress_success_round_robins_aspirations — successes rotate
#       through the declared aspiration tracks ("story" when none declared).
#     * test_choice_pads_to_at_least_two — offer() never returns fewer than 2
#       options: 1-action, empty, and blank inputs all get a synthesized
#       deterministic alternative; property-style loop over levels and sizes.
#     * test_choice_breadth_follows_level — level 0.0 offers 2, 0.5 offers 3,
#       1.0 offers 4 from the same action pool.
#     * test_spark_fires_after_k_same_kind_and_resets — needs_variation()
#       fires only once the last K beats are same-kind, resets on variation,
#       and K shrinks as the dial level rises.
#     * test_spark_twist_is_deterministic — twist(kind) is stable, non-empty,
#       distinct per kind, and covers unknown kinds by construction.
#     * test_challenge_mappings_monotonic — peak_threshold() strictly falls
#       and heat_multiplier() strictly climbs with level; level 0.5 reproduces
#       the stock DirectorEngine feel (threshold 2.5, heat x1.0).
#     * test_dials_build_wires_director — Dials.build() returns configured
#       instances and a DirectorEngine that actually consumes the
#       ChallengeDial: a hard build peaks on the first hot beat, an easy build
#       shrugs the same arc off.
#
# Run:  uv run pytest tests/profiles/game/test_dials.py -v

from __future__ import annotations

import pytest

from soul_protocol.profiles.game import (
    BUILD_UP,
    GRUDGING,
    PEAK,
    ChallengeDial,
    ChoiceGuard,
    Dials,
    DirectorEngine,
    ProgressTracker,
    SparkScheduler,
)
from soul_protocol.profiles.game.dials import GRIT_TRACK, STORY_TRACK

RAGNAR = "did:soul:player:ragnar"


def test_progress_advances_on_failed_beat() -> None:
    """THE evidence rule: a failed beat is still progression — grit and story
    move even when succeeded=False, at every dial level, scaled by the level."""
    tracker = ProgressTracker(["revenge"], level=0.5)
    assert sum(tracker.snapshot().values()) == 0.0

    advanced = tracker.on_beat("betrayal", succeeded=False)
    snap = tracker.snapshot()
    assert advanced  # at least one track moved — the rule itself
    assert snap[GRIT_TRACK] == pytest.approx(0.1)  # 0.1 * (0.5 + 0.5)
    assert snap[STORY_TRACK] == pytest.approx(0.14)  # 0.1 * 1.0 * (0.5 + 0.9)
    assert snap["revenge"] == 0.0  # failure never fakes aspiration progress

    # The guarantee holds at the very bottom of the dial...
    floor = ProgressTracker([], level=0.0)
    assert sum(floor.on_beat("neutral", succeeded=False).values()) > 0.0
    # ...and a higher level advances further for the identical failed beat.
    ceiling = ProgressTracker([], level=1.0)
    ceiling.on_beat("theft", succeeded=False)
    assert ceiling.snapshot()[GRIT_TRACK] > floor.snapshot()[GRIT_TRACK]


def test_progress_success_round_robins_aspirations() -> None:
    """Successes rotate through the declared aspiration tracks; with none
    declared, success advances the implicit story track."""
    tracker = ProgressTracker(["revenge", "romance"], level=0.5)
    tracker.on_beat("neutral", succeeded=True)
    tracker.on_beat("neutral", succeeded=True)
    snap = tracker.snapshot()
    assert snap["revenge"] == pytest.approx(0.1)
    assert snap["romance"] == pytest.approx(0.1)

    bare = ProgressTracker([], level=0.5)
    bare.on_beat("neutral", succeeded=True)
    assert bare.snapshot()[STORY_TRACK] == pytest.approx(0.1)

    # advance() is the manual, unscaled path — it moves exactly what it is told.
    tracker.advance("revenge", 0.5)
    assert tracker.snapshot()["revenge"] == pytest.approx(0.6)


def test_choice_pads_to_at_least_two() -> None:
    """One option is not a choice: offer() synthesizes a deterministic
    alternative whenever fewer than two viable actions come in."""
    guard = ChoiceGuard(level=0.5)

    offered = guard.offer(["confront the butcher"])
    assert offered[0] == "confront the butcher"
    assert offered[1] == "walk away from the butcher"  # deterministic synthesis
    assert len(offered) >= 2

    # Empty and blank-only inputs still produce a real pair of options.
    assert len(guard.offer([])) >= 2
    assert len(guard.offer(["", "   "])) >= 2
    # Synthesis is deterministic: same input, same offer.
    assert guard.offer(["confront the butcher"]) == offered

    # Property-style: never fewer than 2, for any level and any input size.
    for level in (0.0, 0.5, 1.0):
        g = ChoiceGuard(level=level)
        for n in range(6):
            assert len(g.offer([f"action {i}" for i in range(n)])) >= 2


def test_choice_breadth_follows_level() -> None:
    """Higher Choice level widens the offer: 2 at 0.0, 3 at 0.5, 4 at 1.0."""
    actions = [f"action {i}" for i in range(6)]
    assert len(ChoiceGuard(level=0.0).offer(actions)) == 2
    assert len(ChoiceGuard(level=0.5).offer(actions)) == 3
    assert len(ChoiceGuard(level=1.0).offer(actions)) == 4


def test_spark_fires_after_k_same_kind_and_resets() -> None:
    """needs_variation() fires only once the last K beats are same-kind, a
    variation resets it, and K shrinks as the dial level rises."""
    spark = SparkScheduler(level=0.0, window=3)  # most tolerant: K == window == 3
    spark.observe("insult")
    spark.observe("insult")
    assert not spark.needs_variation()  # two in a row is not yet a rut
    spark.observe("insult")
    assert spark.needs_variation()  # three same-kind beats — vary it

    spark.observe("theft")  # variation breaks the streak
    assert not spark.needs_variation()

    # Higher level shrinks K: an immediate repeat already demands variation.
    eager = SparkScheduler(level=1.0, window=5)
    assert eager.k == 2
    eager.observe("insult")
    assert not eager.needs_variation()
    eager.observe("insult")
    assert eager.needs_variation()


def test_spark_twist_is_deterministic() -> None:
    """twist(kind) is stable, non-empty, per-kind distinct, and constructs a
    suggestion for unknown kinds instead of refusing them."""
    spark = SparkScheduler(level=0.5)
    assert spark.twist("insult") == spark.twist("insult")
    assert spark.twist("insult")
    assert spark.twist("insult") != spark.twist("betrayal")
    assert "ambush" in spark.twist("ambush")  # unknown kind still gets a twist


def test_challenge_mappings_monotonic() -> None:
    """Higher challenge => strictly lower peak threshold and strictly hotter
    heat; the midpoint reproduces the stock DirectorEngine feel."""
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    thresholds = [ChallengeDial(lv).peak_threshold() for lv in levels]
    multipliers = [ChallengeDial(lv).heat_multiplier() for lv in levels]

    for easier, harder in zip(thresholds, thresholds[1:]):
        assert harder < easier
    for cooler, hotter in zip(multipliers, multipliers[1:]):
        assert hotter > cooler

    assert ChallengeDial(0.5).peak_threshold() == pytest.approx(2.5)
    assert ChallengeDial(0.5).heat_multiplier() == pytest.approx(1.0)
    # Dials clamp: out-of-range levels stop at the ends.
    assert ChallengeDial(7.0).peak_threshold() == ChallengeDial(1.0).peak_threshold()
    assert ChallengeDial(-3.0).heat_multiplier() == ChallengeDial(0.0).heat_multiplier()


def test_dials_build_wires_director() -> None:
    """Dials.build() returns configured instances, and the DirectorEngine
    genuinely consumes the ChallengeDial: hard peaks on the first hot beat,
    easy shrugs the same arc off."""
    assert Dials() == Dials(challenge=0.5, progress=0.5, choice=0.5, spark=0.5)

    hard = Dials(challenge=1.0).build(aspirations=["survive"])
    assert isinstance(hard.challenge, ChallengeDial)
    assert isinstance(hard.progress, ProgressTracker)
    assert isinstance(hard.choice, ChoiceGuard)
    assert isinstance(hard.spark, SparkScheduler)
    assert isinstance(hard.director, DirectorEngine)
    assert "survive" in hard.progress.snapshot()

    # Hard: threshold 1.0, heat x1.5 -> one GRUDGING betrayal (0.9*1.5*1.5 =
    # 2.025) crosses immediately.
    hard.director.observe_beat(RAGNAR, "betrayal", GRUDGING)
    assert hard.director.phase == PEAK

    # Easy: threshold 4.0, heat x0.5 -> the same three-beat arc stays a build.
    easy = Dials(challenge=0.0).build()
    for _ in range(3):
        easy.director.observe_beat(RAGNAR, "betrayal", GRUDGING)
    assert easy.director.phase == BUILD_UP
    assert easy.director.should_escalate(RAGNAR)
