# __init__.py — Public API for the soul-protocol package
# Updated: feat/soul-encryption — Added SoulEncryptedError and SoulDecryptionError
#   to public imports and __all__ for encrypted .soul file support.
# Updated: v0.5.0 — Two-layer architecture (spec/ + runtime/).
#   spec/ contains protocol primitives (Identity, MemoryStore, SoulContainer, etc.)
#   runtime/ contains the opinionated engine (Soul, Bond, MemoryManager, etc.)
#   All existing public exports preserved for backward compatibility.
#   v0.4.0 — Bond, Skill, SkillRegistry, Eternal storage exports.
#   Core primitive imports (CoreIdentity, CoreMemoryEntry, CoreManifest, DictMemoryStore, MemoryStore).
#   v0.3.2 — Added exception classes to public exports.
#   v0.2.2 — Added SearchStrategy, TokenOverlapStrategy exports. Bumped version.
#   v0.2.1 — Added CognitiveEngine, HeuristicEngine, ReflectionResult exports.
#   v0.2.0 — Added psychology types (SomaticMarker, SignificanceScore,
#   GeneralEvent, SelfImage) to public exports.

from __future__ import annotations

from .runtime.bond import Bond
from .runtime.cognitive.engine import CognitiveEngine, HeuristicEngine
from .runtime.exceptions import (
    SoulCorruptError,
    SoulDecryptionError,
    SoulEncryptedError,
    SoulExportError,
    SoulFileNotFoundError,
    SoulProtocolError,
    SoulRetireError,
)
from .runtime.memory.strategy import SearchStrategy, TokenOverlapStrategy
from .runtime.skills import Skill, SkillRegistry
from .runtime.soul import Soul
from .runtime.types import (
    DNA,
    Biorhythms,
    CommunicationStyle,
    CoreMemory,
    EternalLinks,
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
from .runtime.eternal import ArchiveResult, EternalStorageManager, EternalStorageProvider, RecoverySource

# Core primitives from spec/ (always available — only requires pydantic)
from .spec.identity import Identity as CoreIdentity
from .spec.manifest import Manifest as CoreManifest
from .spec.memory import DictMemoryStore, MemoryStore
from .spec.memory import MemoryEntry as CoreMemoryEntry

__all__ = [
    "Bond",
    "Skill",
    "SkillRegistry",
    "Soul",
    "CognitiveEngine",
    "HeuristicEngine",
    # v0.3.2 exceptions
    "SoulProtocolError",
    "SoulFileNotFoundError",
    "SoulCorruptError",
    "SoulExportError",
    "SoulRetireError",
    # feat/soul-encryption exceptions
    "SoulEncryptedError",
    "SoulDecryptionError",
    # v0.2.2 pluggable retrieval
    "SearchStrategy",
    "TokenOverlapStrategy",
    # Eternal storage
    "ArchiveResult",
    "EternalLinks",
    "EternalStorageManager",
    "EternalStorageProvider",
    "RecoverySource",
    # Types
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
    # Core primitives (v0.4.0)
    "CoreIdentity",
    "CoreManifest",
    "CoreMemoryEntry",
    "DictMemoryStore",
    "MemoryStore",
]

__version__ = "0.2.2"
