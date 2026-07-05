# __init__.py — examples.nemesis_warband: a Shadow-of-Mordor Nemesis System
#   demo built ENTIRELY on the soul_protocol.profiles.game package (imported
#   as-is, zero package edits).
#
# Created: 2026-07-05 (feat/nemesis-warband) — package marker so the example
#   imports as examples.nemesis_warband.* and the tests discover under it.
#   Re-exports NEM-1's building blocks:
#     * Warband / Member (warband.py) — N GrudgeKernel souls with ranks and
#       inter-member grudges, plus the clash loop that promotes/demotes/kills
#       and fires NPC<->NPC jealousy.
"""examples.nemesis_warband — a Nemesis System on top of the Game Profile."""

from .warband import Member, Warband

__all__ = ["Warband", "Member"]
