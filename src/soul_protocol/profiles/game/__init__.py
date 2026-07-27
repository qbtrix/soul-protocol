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
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — PACING + DIALS.
#   Re-exports the Pulse director (DirectorEngine + the BUILD_UP/PEAK/FADE/
#   RELAX phase constants, director.py) and the fun-dial machinery (Dials,
#   BuiltDials, ChallengeDial, ProgressTracker, ChoiceGuard, SparkScheduler,
#   dials.py). BuiltDials rides along as the return type of the public
#   Dials.build(). Still zero core modifications.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — GAME WORLD.
#   Re-exports GameWorld (world.py, the composition root that runs beats
#   through director + kernel + dials and narrates them as the engine-neutral
#   session event stream, state-stream v0) and DEFAULT_ZONE (the zone every
#   soul starts in). Still zero core modifications.

"""The Game Profile — npc.soul + player.soul over the unchanged core.

Two roles on the same ``.soul`` format:

* **npc** — :class:`GrudgeKernel`: a character mind that holds per-player
  grievances (levels ``NONE`` / ``SLIGHTED`` / ``GRUDGING``) across a
  ``.soul`` export -> awaken round-trip, and speaks through a pluggable
  :class:`DialogueEngine`.
* **player** — :class:`PlayerSoul`: a portable identity carrying the
  player's own PUBLIC deeds — reputation (``UNKNOWN`` / ``KNOWN`` /
  ``NOTORIOUS``) any never-met NPC can read and react to.

Around them, the feel layer: :class:`DirectorEngine` (the Pulse director —
deterministic L4D-style pacing over the beat stream) and the four fun dials
(:class:`ChallengeDial`, :class:`ProgressTracker`, :class:`ChoiceGuard`,
:class:`SparkScheduler`), declared and wired through :class:`Dials`.

Normative conventions in ``spec/profiles/game.md``.
"""

from .costmeter import PRICING, CostMeter, ReplayCache
from .dialogue import (
    DialogueEngine,
    LLMDialogueEngine,
    TemplatedDialogueEngine,
    claude_cli_generate,
)
from .dials import (
    BuiltDials,
    ChallengeDial,
    ChoiceGuard,
    Dials,
    ProgressTracker,
    SparkScheduler,
)
from .director import BUILD_UP, FADE, PEAK, RELAX, DirectorEngine
from .grudge import GRUDGING, NONE, SLIGHTED, Grievance, GrudgeKernel
from .player import KNOWN, NOTORIOUS, UNKNOWN, Deed, PlayerSoul
from .world import DEFAULT_ZONE, GameWorld

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
    # the Pulse director (pacing) + its phases
    "DirectorEngine",
    "BUILD_UP",
    "PEAK",
    "FADE",
    "RELAX",
    # the fun dials
    "Dials",
    "BuiltDials",
    "ChallengeDial",
    "ProgressTracker",
    "ChoiceGuard",
    "SparkScheduler",
    # the world (composition + state stream)
    "GameWorld",
    "DEFAULT_ZONE",
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
