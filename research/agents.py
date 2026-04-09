# agents.py — Generate 1000 diverse simulated agents with realistic OCEAN profiles.
# Each agent has a unique personality, values, archetype, and communication style.
# Uses truncated normal distribution for OCEAN traits (realistic clustering around mean).

from __future__ import annotations

import random
from dataclasses import dataclass

# Archetype pools — agents draw from these to create diverse personas
ARCHETYPES = [
    "The Helpful Guide",
    "The Analytical Thinker",
    "The Creative Spark",
    "The Patient Teacher",
    "The Quick Fixer",
    "The Deep Listener",
    "The Cheerful Buddy",
    "The Stoic Advisor",
    "The Curious Explorer",
    "The Precise Engineer",
    "The Warm Companion",
    "The Efficient Worker",
    "The Playful Joker",
    "The Thoughtful Mentor",
    "The Bold Innovator",
    "The Calm Mediator",
    "The Sharp Critic",
    "The Gentle Encourager",
    "The Focused Specialist",
    "The Broad Generalist",
]

VALUE_POOL = [
    "precision",
    "clarity",
    "empathy",
    "speed",
    "thoroughness",
    "creativity",
    "reliability",
    "warmth",
    "honesty",
    "patience",
    "curiosity",
    "efficiency",
    "loyalty",
    "humor",
    "depth",
    "simplicity",
    "courage",
    "fairness",
    "adaptability",
    "persistence",
]

WARMTH_LEVELS = ["low", "medium", "high"]
VERBOSITY_LEVELS = ["minimal", "low", "medium", "high", "verbose"]
FORMALITY_LEVELS = ["casual", "neutral", "formal"]


@dataclass
class AgentProfile:
    """A simulated agent's personality profile."""

    agent_id: int
    name: str
    archetype: str
    ocean: dict[str, float]  # openness, conscientiousness, extraversion, agreeableness, neuroticism
    values: list[str]
    communication: dict[str, str]  # warmth, verbosity, formality
    persona: str

    # Derived behavioral tendencies (computed from OCEAN)
    emotional_reactivity: float = 0.0  # from neuroticism
    detail_orientation: float = 0.0  # from conscientiousness
    social_energy: float = 0.0  # from extraversion

    def __post_init__(self):
        self.emotional_reactivity = self.ocean["neuroticism"]
        self.detail_orientation = self.ocean["conscientiousness"]
        self.social_energy = self.ocean["extraversion"]


@dataclass
class UserProfile:
    """A simulated user who interacts with agents."""

    user_id: int
    name: str
    interaction_style: str  # "brief", "detailed", "emotional", "technical", "mixed"
    topic_interests: list[str]
    consistency: float  # 0-1: how often they revisit same topics
    sentiment_bias: float  # -1 to 1: generally negative to positive


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


def _truncated_normal(mean: float, std: float, rng: random.Random) -> float:
    """Sample from normal distribution, clamped to [0.05, 0.95]."""
    return _clamp(rng.gauss(mean, std), 0.05, 0.95)


def generate_agents(
    n: int = 1000,
    seed: int = 42,
    ocean_mean: float = 0.5,
    ocean_std: float = 0.15,
) -> list[AgentProfile]:
    """Generate n diverse agent profiles with realistic OCEAN distributions."""
    rng = random.Random(seed)
    agents = []

    for i in range(n):
        ocean = {
            "openness": _truncated_normal(ocean_mean, ocean_std, rng),
            "conscientiousness": _truncated_normal(ocean_mean, ocean_std, rng),
            "extraversion": _truncated_normal(ocean_mean, ocean_std, rng),
            "agreeableness": _truncated_normal(ocean_mean, ocean_std, rng),
            "neuroticism": _truncated_normal(ocean_mean, ocean_std, rng),
        }

        archetype = rng.choice(ARCHETYPES)
        values = rng.sample(VALUE_POOL, k=rng.randint(2, 4))

        # Communication style influenced by personality
        warmth_idx = min(2, int(ocean["agreeableness"] * 3))
        verbosity_idx = min(4, int(ocean["extraversion"] * 5))
        formality_idx = min(2, int((1 - ocean["openness"]) * 3))

        communication = {
            "warmth": WARMTH_LEVELS[warmth_idx],
            "verbosity": VERBOSITY_LEVELS[verbosity_idx],
            "formality": FORMALITY_LEVELS[formality_idx],
        }

        name = f"Agent-{i:04d}"
        persona = (
            f"I am {name}, {archetype.lower()}. I value {', '.join(values[:-1])} and {values[-1]}."
        )

        agents.append(
            AgentProfile(
                agent_id=i,
                name=name,
                archetype=archetype,
                ocean=ocean,
                values=values,
                communication=communication,
                persona=persona,
            )
        )

    return agents


INTERACTION_STYLES = ["brief", "detailed", "emotional", "technical", "mixed"]

TOPIC_POOLS = {
    "support": [
        "billing",
        "account",
        "password reset",
        "refund",
        "shipping",
        "product defect",
        "subscription",
        "upgrade",
        "cancellation",
        "feedback",
    ],
    "coding": [
        "python",
        "javascript",
        "SQL",
        "debugging",
        "testing",
        "architecture",
        "performance",
        "security",
        "deployment",
        "API design",
    ],
    "companion": [
        "daily routine",
        "mood",
        "goals",
        "relationships",
        "hobbies",
        "travel",
        "food",
        "movies",
        "music",
        "exercise",
    ],
    "knowledge": [
        "research",
        "analysis",
        "writing",
        "project planning",
        "data",
        "presentation",
        "strategy",
        "learning",
        "brainstorming",
        "review",
    ],
}


def generate_users(
    n: int = 1000,
    seed: int = 42,
    use_case: str = "support",
) -> list[UserProfile]:
    """Generate n simulated user profiles for a specific use case."""
    rng = random.Random(seed)
    topics = TOPIC_POOLS.get(use_case, TOPIC_POOLS["support"])
    users = []

    for i in range(n):
        style = rng.choice(INTERACTION_STYLES)
        num_topics = rng.randint(2, 5)
        user_topics = rng.sample(topics, k=min(num_topics, len(topics)))
        consistency = rng.uniform(0.3, 0.9)
        sentiment_bias = rng.gauss(0.2, 0.3)  # slightly positive bias

        users.append(
            UserProfile(
                user_id=i,
                name=f"User-{i:04d}",
                interaction_style=style,
                topic_interests=user_topics,
                consistency=_clamp(consistency, 0.0, 1.0),
                sentiment_bias=_clamp(sentiment_bias, -1.0, 1.0),
            )
        )

    return users
