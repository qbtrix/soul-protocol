# __init__.py — Public API for the soul-protocol package
# Updated: v0.3.2 — Added exception classes to public exports.
#   v0.2.2 — Added SearchStrategy, TokenOverlapStrategy exports. Bumped version.
#   v0.2.1 — Added CognitiveEngine, HeuristicEngine, ReflectionResult exports.
#   v0.2.0 — Added psychology types (SomaticMarker, SignificanceScore,
#   GeneralEvent, SelfImage) to public exports.

from __future__ import annotations

from .cognitive.engine import CognitiveEngine, HeuristicEngine
from .exceptions import (
    SoulCorruptError,
    SoulExportError,
    SoulFileNotFoundError,
    SoulProtocolError,
    SoulRetireError,
)
from .memory.strategy import SearchStrategy, TokenOverlapStrategy
from .soul import Soul
from .types import (
    DNA,
    Biorhythms,
    CommunicationStyle,
    CoreMemory,
    EvolutionConfig,
    EvolutionMode,
    GeneralEvent,
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    Mood,
    Mutation,
    Personality,
    ReflectionResult,
    SelfImage,
    SignificanceScore,
    SomaticMarker,
    SoulConfig,
    SoulManifest,
    SoulState,
)

__all__ = [
    "Soul",
    "CognitiveEngine",
    "HeuristicEngine",
    # v0.3.2 exceptions
    "SoulProtocolError",
    "SoulFileNotFoundError",
    "SoulCorruptError",
    "SoulExportError",
    "SoulRetireError",
    # v0.2.2 pluggable retrieval
    "SearchStrategy",
    "TokenOverlapStrategy",
    "Biorhythms",
    "CommunicationStyle",
    "CoreMemory",
    "DNA",
    "EvolutionConfig",
    "EvolutionMode",
    "GeneralEvent",
    "Identity",
    "Interaction",
    "LifecycleState",
    "MemoryEntry",
    "MemorySettings",
    "MemoryType",
    "Mood",
    "Mutation",
    "Personality",
    "ReflectionResult",
    "SelfImage",
    "SignificanceScore",
    "SomaticMarker",
    "SoulConfig",
    "SoulManifest",
    "SoulState",
]

__version__ = "0.2.2"
