# dials.py — The four fun dials of the Game Profile: Challenge / Progress /
#   Choice / Spark as composable, continuous 0.0-1.0 dials.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — The evidence-derived
#   feel parameters, each a small deterministic module (no LLM, no network, no
#   randomness) a game runtime composes with the Pulse director:
#     * ChallengeDial(level) — maps the dial to the DirectorEngine tunables:
#       peak_threshold() falls as challenge rises (peaks come sooner) and
#       heat_multiplier() climbs (every beat lands hotter). Anchored so level
#       0.5 reproduces the director's stock feel (threshold 2.5, heat x1.0).
#     * ProgressTracker(aspirations, level) — N overlapping progress tracks.
#       THE evidence rule: on_beat(kind, succeeded) advances at least one track
#       even when succeeded=False — a failed beat still moves the "grit" and
#       "story" tracks (failure-as-progression), scaled by the dial level.
#       Successes advance the caller's aspiration tracks round-robin.
#     * ChoiceGuard(level) — offer(actions) never returns fewer than 2 options:
#       given <2 viable actions it SYNTHESIZES a deterministic alternative
#       ("walk away from <topic>"), because one option is not a choice. Higher
#       levels widen the offer to 3-4.
#     * SparkScheduler(level, window) — variation pressure: needs_variation()
#       fires when the last K beats are same-kind (K shrinks as the dial
#       rises), and twist(kind) suggests a deterministic variation.
#   Dials bundles the four levels (each 0.0-1.0, default 0.5) and build() wires
#   the configured instances — including a DirectorEngine consuming the
#   ChallengeDial. Spec: spec/profiles/game.md (section 8).

"""Challenge / Progress / Choice / Spark — the Game Profile's fun dials.

Each dial is a continuous ``0.0-1.0`` level (out-of-range inputs clamp — a
dial physically stops at its ends) driving one small deterministic module.
:class:`Dials` declares the four levels; :meth:`Dials.build` turns the
declaration into configured instances wired to a :class:`DirectorEngine`.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .director import DirectorEngine
from .grudge import SEVERITY

# ---------------------------------------------------------------------------
# Shared dial plumbing.
# ---------------------------------------------------------------------------


def _clamp(level: float) -> float:
    """Clamp a dial level into [0.0, 1.0] — dials stop at their ends."""
    return min(1.0, max(0.0, float(level)))


# ---------------------------------------------------------------------------
# Challenge — how hard the world pushes back.
# ---------------------------------------------------------------------------

# Threshold endpoints: an easy world needs a long, hot build before it peaks;
# a hard world tips early. Level 0.5 lands on the DirectorEngine default (2.5).
_EASY_PEAK_THRESHOLD = 4.0
_HARD_PEAK_THRESHOLD = 1.0


class ChallengeDial:
    """Maps a 0-1 challenge level onto the director's pacing tunables.

    Higher challenge => LOWER :meth:`peak_threshold` (the scene tips into PEAK
    sooner) and HIGHER :meth:`heat_multiplier` (every beat lands hotter). Both
    mappings are linear and anchored so level 0.5 reproduces the stock
    :class:`DirectorEngine` feel (threshold 2.5, heat x1.0).
    """

    def __init__(self, level: float = 0.5) -> None:
        self.level = _clamp(level)

    def peak_threshold(self) -> float:
        """Peak threshold for the director: 4.0 at level 0.0 down to 1.0 at 1.0."""
        return _EASY_PEAK_THRESHOLD + (_HARD_PEAK_THRESHOLD - _EASY_PEAK_THRESHOLD) * self.level

    def heat_multiplier(self) -> float:
        """Per-beat heat scale: 0.5 at level 0.0 up to 1.5 at level 1.0."""
        return 0.5 + self.level


# ---------------------------------------------------------------------------
# Progress — visible motion on overlapping tracks, even through failure.
# ---------------------------------------------------------------------------

# Implicit tracks every tracker carries alongside the caller's aspirations.
STORY_TRACK = "story"
GRIT_TRACK = "grit"

# Base advancement per beat before the dial scale (0.5 + level) is applied.
_BEAT_PROGRESS = 0.1


class ProgressTracker:
    """N overlapping progress tracks with failure-as-progression.

    ``aspirations`` name the caller's tracks (a quest, a relationship, a
    skill); the implicit ``story`` and ``grit`` tracks always exist too. THE
    evidence rule: :meth:`on_beat` advances at least one track even when
    ``succeeded=False`` — a failed beat forges ``grit`` and still moves the
    ``story`` (weighted by the beat's :data:`~.grudge.SEVERITY`, a failed
    betrayal is a bigger story beat than a failed greeting). All advancement
    scales with the dial level via ``(0.5 + level)``, which never reaches
    zero, so the guarantee holds at every dial setting.
    """

    def __init__(self, aspirations: list[str], level: float = 0.5) -> None:
        self.level = _clamp(level)
        self._aspirations = list(aspirations)
        self._tracks: dict[str, float] = dict.fromkeys(self._aspirations, 0.0)
        self._tracks.setdefault(STORY_TRACK, 0.0)
        self._tracks.setdefault(GRIT_TRACK, 0.0)
        self._round_robin = 0

    def advance(self, track: str, amount: float) -> float:
        """Advance one track by ``amount`` (creating it if new); returns its
        new value. Manual advances are verbatim — the dial scale applies only
        to :meth:`on_beat`."""
        self._tracks[track] = self._tracks.get(track, 0.0) + float(amount)
        return self._tracks[track]

    def on_beat(self, kind: str, succeeded: bool) -> dict[str, float]:
        """Advance tracks for one beat; returns ``{track: amount}`` advanced.

        Success moves the next aspiration track (round-robin; ``story`` when
        no aspirations were declared). Failure ALWAYS moves ``grit`` and
        ``story`` — at least one track advances on every beat, succeeded or
        not. That is the dial's evidence rule: failing forward is progression.
        """
        base = _BEAT_PROGRESS * (0.5 + self.level)
        if succeeded:
            advanced = {self._next_success_track(): base}
        else:
            advanced = {
                GRIT_TRACK: base,
                STORY_TRACK: base * (0.5 + SEVERITY.get(kind, 0.0)),
            }
        for track, amount in advanced.items():
            self.advance(track, amount)
        return advanced

    def snapshot(self) -> dict[str, float]:
        """A copy of every track's current progress."""
        return dict(self._tracks)

    def _next_success_track(self) -> str:
        if not self._aspirations:
            return STORY_TRACK
        track = self._aspirations[self._round_robin % len(self._aspirations)]
        self._round_robin += 1
        return track


# ---------------------------------------------------------------------------
# Choice — one option is not a choice.
# ---------------------------------------------------------------------------


class ChoiceGuard:
    """Guarantees every offer holds at least two viable actions.

    :meth:`offer` filters blank actions, caps breadth by the dial (level 0.0
    offers 2, 0.5 offers 3, 1.0 offers 4 — more choice at higher settings),
    and when fewer than two viable actions were passed it SYNTHESIZES a
    deterministic alternative — a "walk away from <topic>" construction off
    the first action (or a stock stand-your-ground option when none were
    given). The return is always >= 2 options.
    """

    def __init__(self, level: float = 0.5) -> None:
        self.level = _clamp(level)
        self.max_offered = 2 + int(self.level * 2 + 0.5)

    def offer(self, actions: list[str]) -> list[str]:
        """At least two, at most ``max_offered``, always deterministic."""
        offered = [a for a in actions if a and a.strip()][: self.max_offered]
        while len(offered) < 2:
            offered.append(self._synthesize(offered))
        return offered

    @staticmethod
    def _synthesize(offered: list[str]) -> str:
        """A deterministic alternative built from what is already on offer."""
        if not offered:
            return "hold your ground"
        first = offered[0]
        topic = " ".join(first.split()[1:]) or first
        alternative = f"walk away from {topic}"
        if alternative in offered:  # keep the pair distinct, still deterministic
            alternative = f"{alternative} instead"
        return alternative


# ---------------------------------------------------------------------------
# Spark — variation pressure against same-kind monotony.
# ---------------------------------------------------------------------------

# Deterministic variation suggestions for the profile's known beat kinds.
_TWISTS: dict[str, str] = {
    "neutral": "interrupt the calm: an old debt comes due mid-sentence",
    "insult": "let the insult land on an unintended ear",
    "theft": "the stolen thing turns out to matter more than it looked",
    "betrayal": "reveal the betrayal cut both ways",
}


class SparkScheduler:
    """Fires when the recent beats have gone same-kind stale.

    Tracks the last ``window`` beat kinds via :meth:`observe`.
    :meth:`needs_variation` is True when the last ``k`` beats are all the same
    kind, where ``k`` shrinks from ``window`` (level 0.0, tolerant) down to 2
    (level 1.0, an immediate repeat already demands a change). Any different
    kind breaks the streak. :meth:`twist` suggests a deterministic variation
    for the repeated kind.
    """

    def __init__(self, level: float = 0.5, window: int = 5) -> None:
        self.level = _clamp(level)
        self.window = max(2, int(window))
        self.k = max(2, self.window - int(self.level * (self.window - 2)))
        self._recent: deque[str] = deque(maxlen=self.window)

    def observe(self, kind: str) -> None:
        """Record one beat kind."""
        self._recent.append(kind)

    def needs_variation(self) -> bool:
        """True when the last ``k`` observed beats are all the same kind."""
        if len(self._recent) < self.k:
            return False
        tail = list(self._recent)[-self.k :]
        return len(set(tail)) == 1

    def twist(self, kind: str) -> str:
        """A deterministic variation suggestion for a repeated kind."""
        return _TWISTS.get(kind, f"vary the {kind} beat: change who pays its price")


# ---------------------------------------------------------------------------
# The bundle — declare four levels, build the configured machinery.
# ---------------------------------------------------------------------------


@dataclass
class BuiltDials:
    """The configured instances :meth:`Dials.build` returns, ready to run."""

    challenge: ChallengeDial
    progress: ProgressTracker
    choice: ChoiceGuard
    spark: SparkScheduler
    director: DirectorEngine


@dataclass(frozen=True)
class Dials:
    """The declared feel of a world: four continuous dials, 0.0-1.0 each.

    Defaults sit at 0.5 — the tuned baseline (a :class:`ChallengeDial` at 0.5
    reproduces the stock :class:`DirectorEngine`). Levels outside the range
    clamp inside the modules they configure.
    """

    challenge: float = 0.5
    progress: float = 0.5
    choice: float = 0.5
    spark: float = 0.5

    def build(
        self,
        aspirations: list[str] | None = None,
        enjoyment_signal: Callable[[str], float] | None = None,
    ) -> BuiltDials:
        """Wire the configured instances — the director consumes the
        :class:`ChallengeDial` (threshold + heat), and the optional
        ``enjoyment_signal`` hook passes straight through to it."""
        challenge = ChallengeDial(self.challenge)
        return BuiltDials(
            challenge=challenge,
            progress=ProgressTracker(list(aspirations or []), level=self.progress),
            choice=ChoiceGuard(self.choice),
            spark=SparkScheduler(self.spark),
            director=DirectorEngine(challenge=challenge, enjoyment_signal=enjoyment_signal),
        )
