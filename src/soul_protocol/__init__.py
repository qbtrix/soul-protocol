# __init__.py — Public API for the soul-protocol package
# Updated: 2026-03-06 — Added Bond, Skill, SkillRegistry exports

from __future__ import annotations

from .bond import Bond
from .skills import Skill, SkillRegistry
from .soul import Soul
from .types import (
    Biorhythms,
    CommunicationStyle,
    CoreMemory,
    DNA,
    EvolutionConfig,
    EvolutionMode,
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    Mood,
    Mutation,
    Personality,
    SoulConfig,
    SoulManifest,
    SoulState,
)

__all__ = [
    "Bond",
    "Skill",
    "SkillRegistry",
    "Soul",
    "Biorhythms",
    "CommunicationStyle",
    "CoreMemory",
    "DNA",
    "EvolutionConfig",
    "EvolutionMode",
    "Identity",
    "Interaction",
    "LifecycleState",
    "MemoryEntry",
    "MemorySettings",
    "MemoryType",
    "Mood",
    "Mutation",
    "Personality",
    "SoulConfig",
    "SoulManifest",
    "SoulState",
]

__version__ = "0.1.0"
