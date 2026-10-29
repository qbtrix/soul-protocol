# soul_protocol.optimize — Autonomous self-improvement loop using eval signal.
# Created: 2026-04-29 (#142) — Builds on the soul-aware eval framework
#   (#160) so a soul can run an eval against itself, propose changes to
#   its own knobs (OCEAN traits, persona text, memory thresholds, bond
#   strength), keep changes that move the eval score up, and revert those
#   that don't. Pairs with #160: without the eval, "improvement" is a
#   vibe; with the eval, it's a number that can go up.
#
# The public surface mirrors soul_protocol.eval — a small set of types
# and a single async entry point (``optimize``). Knobs are pluggable via
# :class:`OptimizeRunner.register_knob`.

from __future__ import annotations

from .knobs import (
    BondThresholdKnob,
    Knob,
    OceanTraitKnob,
    PersonaTextKnob,
    SignificanceThresholdKnob,
    default_knobs,
)
from .proposer import Proposer
from .runner import OptimizeRunner, optimize, score_of
from .types import KnobProposal, OptimizeResult, OptimizeStep

__all__ = [
    # Public types
    "OptimizeResult",
    "OptimizeStep",
    "KnobProposal",
    # Knobs
    "Knob",
    "OceanTraitKnob",
    "PersonaTextKnob",
    "SignificanceThresholdKnob",
    "BondThresholdKnob",
    "default_knobs",
    # Proposer
    "Proposer",
    # Runner
    "OptimizeRunner",
    "optimize",
    "score_of",
]
