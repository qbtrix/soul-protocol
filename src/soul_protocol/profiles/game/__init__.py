# __init__.py — soul_protocol.profiles.game: the Game Profile public API.
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — graduates the
#   examples/npc_soul_grudge experiment into the first Soul Protocol profile.
#   Re-exports the two roles (GrudgeKernel = npc, PlayerSoul = player), the
#   DialogueEngine seam + engines, the cost instrumentation (CostMeter,
#   ReplayCache, PRICING), and the grudge-level / notoriety constants.
#   Grievance and Deed ride along because they are the return types of the
#   public GrudgeKernel.grievances() / PlayerSoul.deeds() accessors.
#   Zero core files were modified to build this profile. Spec:
#   spec/profiles/game.md.

"""The Game Profile — npc.soul + player.soul over the unchanged core.

Two roles on the same ``.soul`` format:

* **npc** — :class:`GrudgeKernel`: a character mind that holds per-player
  grievances (levels ``NONE`` / ``SLIGHTED`` / ``GRUDGING``) across a
  ``.soul`` export -> awaken round-trip, and speaks through a pluggable
  :class:`DialogueEngine`.
* **player** — :class:`PlayerSoul`: a portable identity carrying the
  player's own PUBLIC deeds — reputation (``UNKNOWN`` / ``KNOWN`` /
  ``NOTORIOUS``) any never-met NPC can read and react to.

Normative conventions in ``spec/profiles/game.md``.
"""

from .costmeter import PRICING, CostMeter, ReplayCache
from .dialogue import (
    DialogueEngine,
    LLMDialogueEngine,
    TemplatedDialogueEngine,
    claude_cli_generate,
)
from .grudge import GRUDGING, NONE, SLIGHTED, Grievance, GrudgeKernel
from .player import KNOWN, NOTORIOUS, UNKNOWN, Deed, PlayerSoul

__all__ = [
    # roles
    "GrudgeKernel",
    "PlayerSoul",
    # dialogue seam
    "DialogueEngine",
    "TemplatedDialogueEngine",
    "LLMDialogueEngine",
    "claude_cli_generate",
    # cost instrumentation
    "CostMeter",
    "ReplayCache",
    "PRICING",
    # grudge levels (npc)
    "NONE",
    "SLIGHTED",
    "GRUDGING",
    # notoriety bands (player)
    "UNKNOWN",
    "KNOWN",
    "NOTORIOUS",
    # record types returned by the public accessors
    "Grievance",
    "Deed",
]
