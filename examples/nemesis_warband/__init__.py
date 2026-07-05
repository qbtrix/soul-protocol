# __init__.py — examples.nemesis_warband: a Shadow-of-Mordor Nemesis System
#   demo built ENTIRELY on the soul_protocol.profiles.game package (imported
#   as-is, zero package edits).
#
# Created: 2026-07-05 (feat/nemesis-warband) — package marker so the example
#   imports as examples.nemesis_warband.* and the tests discover under it.
#   Re-exports NEM-1's building blocks (Warband / Member).
#
# Updated: 2026-07-05 (feat/nemesis-warband) — NEM-2: also re-export
#   WarbandDirector (nemesis_director.py), which wraps DirectorEngine to
#   schedule revenge beats (the highest-grudge alive member hunts the player)
#   and power struggles (same-rank rivals challenge for rank), all as pure
#   deterministic functions of grudge/rank state.
#
# Updated: 2026-07-05 (feat/nemesis-warband) — NEM-3: re-export the warband's
#   OWN voice, WarbandDialogueEngine (warband_voice.py) — a grimdark,
#   name/epithet/rank-aware DialogueEngine plug that replaces the package's
#   butcher/"Bjorn" template WITHOUT touching the package. forge() wires it per
#   member by default.
"""examples.nemesis_warband — a Nemesis System on top of the Game Profile."""

from .nemesis_director import WarbandDirector
from .warband import Member, Warband
from .warband_voice import WarbandDialogueEngine

__all__ = ["Warband", "Member", "WarbandDirector", "WarbandDialogueEngine"]
