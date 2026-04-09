# config.py — Experiment configuration: conditions, metrics, hyperparameters.
# All experiment parameters live here so runs are fully reproducible.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MemoryCondition(StrEnum):
    """The 5 experimental conditions (independent variable)."""

    NONE = "none"  # No memory at all (stateless baseline)
    RAG_ONLY = "rag_only"  # Pure vector similarity retrieval
    RAG_SIGNIFICANCE = "rag_sig"  # RAG + LIDA significance gating
    FULL_NO_EMOTION = "full_no_emo"  # Full pipeline minus somatic markers
    FULL_SOUL = "full_soul"  # Complete Soul Protocol stack


class UseCase(StrEnum):
    """The 4 evaluation domains."""

    CUSTOMER_SUPPORT = "support"
    CODING_ASSISTANT = "coding"
    PERSONAL_COMPANION = "companion"
    KNOWLEDGE_WORKER = "knowledge"


@dataclass
class ExperimentConfig:
    """Top-level experiment configuration."""

    # Scale
    num_agents: int = 1000
    interactions_per_agent: int = 50
    num_sessions: int = 5  # sessions per agent (tests cross-session recall)
    interactions_per_session: int = 10

    # Conditions
    conditions: list[MemoryCondition] = field(default_factory=lambda: list(MemoryCondition))
    use_cases: list[UseCase] = field(default_factory=lambda: list(UseCase))

    # Reproducibility
    random_seed: int = 42

    # Memory pipeline thresholds (used by FULL conditions)
    significance_threshold: float = 0.3
    activation_decay_rate: float = 0.95

    # Personality generation
    ocean_mean: float = 0.5
    ocean_std: float = 0.15  # produces realistic spread (most between 0.2-0.8)

    # Output
    output_dir: str = "research/results"

    @property
    def total_runs(self) -> int:
        return self.num_agents * len(self.conditions) * len(self.use_cases)

    @property
    def total_interactions(self) -> int:
        return self.total_runs * self.interactions_per_agent
