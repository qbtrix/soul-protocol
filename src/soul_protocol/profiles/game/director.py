# director.py — The Pulse director: an L4D-style pacing engine for the Game
#   Profile, over the unchanged Soul Protocol core.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Implements Valve's
#   AI-director algorithm (GDC 2009, Left 4 Dead) on the grudge kernel's beat
#   stream: pace event FREQUENCY, not amplitude. The scene cycles
#   BUILD_UP -> PEAK -> FADE -> RELAX; only BUILD_UP green-lights new stress
#   events (should_escalate() is the frequency governor), and RELAX is the
#   mandatory low-intensity window — no escalation there, no matter how hot the
#   intensity reads. Per-player intensity is a deterministic float: each
#   observe_beat(player_did, kind, grudge_level) decays the player's value by a
#   configurable factor, then adds heat from the shared SEVERITY table
#   (betrayal > theft > insult > neutral ~ small floor) amplified by the grudge
#   level (GRUDGING lands hottest). Layered on top: Monolith's "yes-and" rule —
#   yes_and(kind) NEVER vetoes a player action, it always returns a build-on
#   suggestion — and an optional enjoyment_signal hook (0..1 per player) that
#   scales the peak threshold (bored players peak sooner, delighted players get
#   a longer build). Zero LLM, zero network, zero randomness — every method is
#   a pure function of the observed beat sequence and the constructor tunables.
#   Spec: spec/profiles/game.md (section 8).
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — DIALS WIRING. The
#   constructor gains an optional challenge=ChallengeDial (dials.py): when
#   provided, the dial derives peak_threshold (overriding an explicit value)
#   and its heat_multiplier() scales every beat's heat, so one 0-1 Challenge
#   dial retunes the whole pacing feel. Behavior without the param is
#   unchanged (heat scale 1.0). Import is TYPE_CHECKING-only — dials.py
#   imports this module at runtime, not the other way around.

"""The Pulse director — deterministic L4D-style pacing over grudge beats.

One :class:`DirectorEngine` paces one scene. Feed it every player action via
:meth:`DirectorEngine.observe_beat`; read back ``phase``,
:meth:`~DirectorEngine.intensity`, :meth:`~DirectorEngine.should_escalate`,
:meth:`~DirectorEngine.suggest_pacing`, and :meth:`~DirectorEngine.yes_and`.
The phase is scene-global (a director paces the whole scene, driven by
whichever relationship runs hottest); intensity is tracked per player.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .grudge import GRUDGING, NONE, SEVERITY, SLIGHTED

if TYPE_CHECKING:  # typing only — dials.py imports this module at runtime.
    from .dials import ChallengeDial

# ---------------------------------------------------------------------------
# Phases — the L4D pacing cycle. BUILD_UP is the only phase in which the
# director green-lights new stress events; PEAK is held for a bounded number
# of beats, FADE releases, and RELAX is the mandatory quiet window.
# ---------------------------------------------------------------------------
BUILD_UP = "BUILD_UP"
PEAK = "PEAK"
FADE = "FADE"
RELAX = "RELAX"

PHASES: tuple[str, ...] = (BUILD_UP, PEAK, FADE, RELAX)

# Phase -> pacing verb, the vocabulary suggest_pacing() speaks.
PACING_BY_PHASE: dict[str, str] = {
    BUILD_UP: "escalate",
    PEAK: "sustain",
    FADE: "release",
    RELAX: "rest",
}

# A beat of ANY kind stimulates a little (a scene where things happen is never
# fully cold); SEVERITY supplies the real heat above this floor.
NEUTRAL_HEAT = 0.05

# Grudge context amplifies heat: the same wrong lands hotter on an already
# GRUDGING relationship. Unknown levels read as NONE — never reject an input.
GRUDGE_HEAT_MULTIPLIER: dict[str, float] = {
    NONE: 1.0,
    SLIGHTED: 1.2,
    GRUDGING: 1.5,
}

# Monolith's "yes-and" rule: the director never negates a player action, it
# builds on it. Known kinds map to a curated suggestion; unknown kinds get a
# deterministic constructed one (see DirectorEngine.yes_and) — never a veto.
YES_AND_BUILDS: dict[str, str] = {
    "neutral": "deepen",
    "insult": "sharpen",
    "theft": "pursue",
    "betrayal": "consequence",
}


class DirectorEngine:
    """Deterministic pacing state machine over the beat stream of one scene.

    Tunables (constructor):

    * ``peak_threshold`` — intensity at which BUILD_UP tips into PEAK.
    * ``decay`` — per-beat retention factor in ``(0, 1]``; a player's intensity
      is multiplied by it before the new beat's heat is added, so quiet beats
      cool the scene.
    * ``peak_beats`` / ``fade_beats`` / ``relax_beats`` — how many observed
      beats each post-build phase lasts (each phase reports itself for exactly
      that many beats before handing over).
    * ``enjoyment_signal`` — optional ``(player_did) -> 0..1`` hook. When
      provided, the effective peak threshold becomes
      ``peak_threshold * (0.5 + signal)``: a bored player (0.0) peaks at half
      the threshold, a delighted one (1.0) earns a 1.5x longer build. ``None``
      (the v0 default) is the pure intensity model, identical to a constant
      signal of 0.5.
    * ``challenge`` — optional :class:`~.dials.ChallengeDial`. When provided,
      the dial IS the tuning knob: it derives ``peak_threshold`` (overriding
      an explicitly passed value) and scales every beat's heat by its
      ``heat_multiplier()``.
    """

    def __init__(
        self,
        peak_threshold: float = 2.5,
        decay: float = 0.85,
        peak_beats: int = 4,
        fade_beats: int = 2,
        relax_beats: int = 5,
        enjoyment_signal: Callable[[str], float] | None = None,
        challenge: ChallengeDial | None = None,
    ) -> None:
        if challenge is not None:
            peak_threshold = challenge.peak_threshold()
            self._heat_scale = challenge.heat_multiplier()
        else:
            self._heat_scale = 1.0
        if peak_threshold <= 0:
            raise ValueError(f"peak_threshold must be > 0, got {peak_threshold!r}")
        if not 0.0 < decay <= 1.0:
            raise ValueError(f"decay must be in (0.0, 1.0], got {decay!r}")
        if peak_beats < 1 or fade_beats < 1 or relax_beats < 1:
            raise ValueError("peak_beats, fade_beats and relax_beats must each be >= 1")
        self.peak_threshold = peak_threshold
        self.decay = decay
        self.peak_beats = peak_beats
        self.fade_beats = fade_beats
        self.relax_beats = relax_beats
        self.enjoyment_signal = enjoyment_signal
        self._phase = BUILD_UP
        self._beats_in_phase = 0
        self._intensity: dict[str, float] = {}

    # ---- readouts ----------------------------------------------------------

    @property
    def phase(self) -> str:
        """The scene's current pacing phase (one of :data:`PHASES`)."""
        return self._phase

    def intensity(self, player_did: str) -> float:
        """This player's current intensity (0.0 for a player never observed)."""
        return self._intensity.get(player_did, 0.0)

    # ---- the beat clock ----------------------------------------------------

    def observe_beat(self, player_did: str, kind: str, grudge_level: str = NONE) -> float:
        """Feed one player action into the director; returns the new intensity.

        Heat = ``max(SEVERITY[kind], NEUTRAL_HEAT)`` (unknown kinds read as
        neutral — yes-and: the director never rejects an observed action)
        amplified by the grudge level and by the challenge dial's heat
        multiplier when one was wired in. The player's intensity decays by the
        configured factor, the heat lands, and then the phase machine advances:
        BUILD_UP tips into PEAK when this player's intensity crosses their
        effective threshold; PEAK, FADE and RELAX each last their configured
        number of beats.
        """
        heat = max(SEVERITY.get(kind, 0.0), NEUTRAL_HEAT)
        heat *= GRUDGE_HEAT_MULTIPLIER.get(grudge_level, 1.0) * self._heat_scale
        value = self._intensity.get(player_did, 0.0) * self.decay + heat
        self._intensity[player_did] = value
        self._advance_phase(player_did)
        return value

    def _advance_phase(self, player_did: str) -> None:
        """One tick of the phase machine, clocked by observed beats."""
        if self._phase == BUILD_UP:
            if self._intensity[player_did] >= self._effective_threshold(player_did):
                self._enter(PEAK)
        elif self._phase == PEAK:
            self._beats_in_phase += 1
            if self._beats_in_phase >= self.peak_beats:
                self._enter(FADE)
        elif self._phase == FADE:
            self._beats_in_phase += 1
            if self._beats_in_phase >= self.fade_beats:
                self._enter(RELAX)
        else:  # RELAX — the mandatory quiet window, then a fresh build.
            self._beats_in_phase += 1
            if self._beats_in_phase >= self.relax_beats:
                self._enter(BUILD_UP)

    def _enter(self, phase: str) -> None:
        self._phase = phase
        self._beats_in_phase = 0

    # ---- the frequency governor --------------------------------------------

    def should_escalate(self, player_did: str) -> bool:
        """True ONLY in BUILD_UP while this player is below their effective
        peak threshold — the frequency governor. In PEAK/FADE/RELAX (and in
        BUILD_UP at or above the ceiling) the answer is False regardless of
        how hot the intensity reads."""
        return self._phase == BUILD_UP and self._intensity.get(
            player_did, 0.0
        ) < self._effective_threshold(player_did)

    def suggest_pacing(self, player_did: str) -> str:
        """The phase's pacing verb: ``escalate`` / ``sustain`` / ``release`` /
        ``rest`` (see :data:`PACING_BY_PHASE`). In BUILD_UP, a player already
        at/over their effective threshold gets ``sustain`` instead of
        ``escalate`` so this readout never contradicts
        :meth:`should_escalate`."""
        if self._phase == BUILD_UP and not self.should_escalate(player_did):
            return PACING_BY_PHASE[PEAK]
        return PACING_BY_PHASE[self._phase]

    # ---- yes-and ------------------------------------------------------------

    def yes_and(self, action_kind: str) -> str:
        """A build-on suggestion for ANY action kind — never a veto.

        Known kinds map through :data:`YES_AND_BUILDS` (``neutral -> deepen``,
        ``betrayal -> consequence``, ...); unknown kinds get a deterministic
        constructed suggestion that still builds on the action. The director
        never negates what a player did.
        """
        return YES_AND_BUILDS.get(action_kind, f"build-on-{action_kind}")

    # ---- internals -----------------------------------------------------------

    def _effective_threshold(self, player_did: str) -> float:
        """The peak threshold, scaled by the enjoyment hook when present."""
        if self.enjoyment_signal is None:
            return self.peak_threshold
        signal = min(1.0, max(0.0, float(self.enjoyment_signal(player_did))))
        return self.peak_threshold * (0.5 + signal)
