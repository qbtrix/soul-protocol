# metrics.py — Metric collection and statistical analysis.
# 6 metric categories: retrieval, emotional, personality, memory efficiency, bond, skills.
# All metrics are collected per-agent, per-condition, per-use-case for full factorial analysis.

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecallMetrics:
    """How well the system retrieves relevant information."""

    # Precision: of returned memories, how many were relevant?
    precision_scores: list[float] = field(default_factory=list)
    # Recall: of planted facts, how many were retrieved?
    recall_scores: list[float] = field(default_factory=list)
    # Was the exact planted fact found in the top-k results?
    hit_at_k: list[bool] = field(default_factory=list)
    # How many turns after planting before the fact is retrievable?
    retrieval_latency: list[int] = field(default_factory=list)

    @property
    def mean_precision(self) -> float:
        return statistics.mean(self.precision_scores) if self.precision_scores else 0.0

    @property
    def mean_recall(self) -> float:
        return statistics.mean(self.recall_scores) if self.recall_scores else 0.0

    @property
    def hit_rate(self) -> float:
        return sum(self.hit_at_k) / len(self.hit_at_k) if self.hit_at_k else 0.0


@dataclass
class EmotionalMetrics:
    """How well the system tracks and responds to emotional context."""

    # Did somatic marker match the expected emotion?
    emotion_accuracy: list[bool] = field(default_factory=list)
    # Valence tracking over time (should correlate with sentiment changes)
    valence_trajectory: list[float] = field(default_factory=list)
    # Does bond strength correlate with positive interactions?
    bond_correlation: float = 0.0

    @property
    def emotion_accuracy_rate(self) -> float:
        return (
            sum(self.emotion_accuracy) / len(self.emotion_accuracy)
            if self.emotion_accuracy
            else 0.0
        )


@dataclass
class PersonalityMetrics:
    """How stable and consistent is personality expression?"""

    # OCEAN trait drift over time (should be low for stable personalities)
    trait_drift: dict[str, list[float]] = field(default_factory=dict)
    # Communication style consistency (measured by output characteristics)
    style_consistency: list[float] = field(default_factory=list)

    @property
    def mean_drift(self) -> float:
        all_drifts = []
        for drifts in self.trait_drift.values():
            all_drifts.extend(drifts)
        return statistics.mean(all_drifts) if all_drifts else 0.0


@dataclass
class MemoryEfficiencyMetrics:
    """How efficiently does the system use memory?"""

    # Total memories stored vs. total interactions
    memory_growth_rate: list[tuple[int, int]] = field(default_factory=list)
    # How many memories are actually useful (retrieved at least once)?
    memory_utilization: float = 0.0
    # Significance scores distribution
    significance_scores: list[float] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        """Interactions per stored memory (higher = more selective)."""
        if not self.memory_growth_rate:
            return 0.0
        interactions, memories = self.memory_growth_rate[-1]
        return interactions / memories if memories > 0 else 0.0


@dataclass
class BondMetrics:
    """Bond formation and evolution tracking."""

    strength_trajectory: list[float] = field(default_factory=list)
    interaction_count_at_milestones: dict[int, int] = field(default_factory=dict)

    @property
    def final_strength(self) -> float:
        return self.strength_trajectory[-1] if self.strength_trajectory else 0.0

    @property
    def growth_rate(self) -> float:
        if len(self.strength_trajectory) < 2:
            return 0.0
        return (self.strength_trajectory[-1] - self.strength_trajectory[0]) / len(
            self.strength_trajectory
        )


@dataclass
class SkillMetrics:
    """Skill acquisition and development tracking."""

    skills_discovered: int = 0
    total_xp: int = 0
    max_level: int = 0
    skill_names: list[str] = field(default_factory=list)


@dataclass
class AgentRunMetrics:
    """Complete metrics for one agent under one condition in one use case."""

    agent_id: int
    condition: str
    use_case: str
    recall: RecallMetrics = field(default_factory=RecallMetrics)
    emotional: EmotionalMetrics = field(default_factory=EmotionalMetrics)
    personality: PersonalityMetrics = field(default_factory=PersonalityMetrics)
    efficiency: MemoryEfficiencyMetrics = field(default_factory=MemoryEfficiencyMetrics)
    bond: BondMetrics = field(default_factory=BondMetrics)
    skills: SkillMetrics = field(default_factory=SkillMetrics)

    def to_row(self) -> dict[str, Any]:
        """Flatten to a single row for tabular analysis."""
        return {
            "agent_id": self.agent_id,
            "condition": self.condition,
            "use_case": self.use_case,
            # Recall
            "recall_precision": self.recall.mean_precision,
            "recall_recall": self.recall.mean_recall,
            "recall_hit_rate": self.recall.hit_rate,
            # Emotional
            "emotion_accuracy": self.emotional.emotion_accuracy_rate,
            "bond_final": self.bond.final_strength,
            "bond_growth_rate": self.bond.growth_rate,
            # Personality
            "personality_drift": self.personality.mean_drift,
            # Efficiency
            "memory_compression": self.efficiency.compression_ratio,
            "memory_count": self.efficiency.memory_growth_rate[-1][1]
            if self.efficiency.memory_growth_rate
            else 0,
            # Skills
            "skills_discovered": self.skills.skills_discovered,
            "skills_max_level": self.skills.max_level,
        }


# ---------------------------------------------------------------------------
# Statistical utilities
# ---------------------------------------------------------------------------


def cohens_d(group1: list[float], group2: list[float]) -> float:
    """Calculate Cohen's d effect size between two groups."""
    if not group1 or not group2:
        return 0.0
    n1, n2 = len(group1), len(group2)
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1 = statistics.variance(group1) if n1 > 1 else 0.0
    var2 = statistics.variance(group2) if n2 > 1 else 0.0
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (mean1 - mean2) / pooled_std


def confidence_interval_95(data: list[float]) -> tuple[float, float]:
    """Calculate 95% confidence interval using t-distribution approximation."""
    if len(data) < 2:
        return (0.0, 0.0)
    n = len(data)
    mean = statistics.mean(data)
    se = statistics.stdev(data) / math.sqrt(n)
    # t-value for 95% CI with large n ~ 1.96
    t_val = 1.96 if n > 30 else 2.0
    return (mean - t_val * se, mean + t_val * se)


def mann_whitney_u(x: list[float], y: list[float]) -> tuple[float, float]:
    """Simplified Mann-Whitney U test (non-parametric comparison).

    Returns (U statistic, approximate p-value using normal approximation).
    For publication, use scipy.stats.mannwhitneyu instead.
    """
    if not x or not y:
        return (0.0, 1.0)

    nx, ny = len(x), len(y)
    # Combine and rank
    combined = [(val, "x") for val in x] + [(val, "y") for val in y]
    combined.sort(key=lambda t: t[0])

    # Assign ranks (handle ties with average rank)
    ranks: dict[str, list[float]] = {"x": [], "y": []}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2  # 1-indexed average
        for k in range(i, j):
            ranks[combined[k][1]].append(avg_rank)
        i = j

    r1 = sum(ranks["x"])
    u1 = r1 - nx * (nx + 1) / 2
    u2 = nx * ny - u1

    u = min(u1, u2)

    # Normal approximation for p-value
    mu = nx * ny / 2
    sigma = math.sqrt(nx * ny * (nx + ny + 1) / 12)
    if sigma == 0:
        return (u, 1.0)
    z = (u - mu) / sigma
    # Two-tailed p-value approximation
    p = 2 * (1 - _norm_cdf(abs(z)))

    return (u, p)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
