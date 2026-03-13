# memory/activation.py — ACT-R activation-based memory scoring.
# Updated: v0.3.4-fix — Salience now uses additive boost instead of multiplicative.
#   Fixes bug where multiplying negative base by salience amplified the penalty.
#   High salience always helps activation, never hurts it. Replaced getattr with
#   direct field access since salience is a Pydantic field with default 0.5.
# Updated: v0.3.3 — Added personality parameter to compute_activation().
#   Personality-modulated boost from OCEAN traits influences recall ranking.
#   Backwards compatible: personality=None produces identical scores to before.
# Updated: phase1-ablation-fixes — Added importance/significance boost (0.3 * sig),
#   increased spreading weight from 1.5 to 2.0 for better BM25 integration.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.2 — Accept optional SearchStrategy for pluggable spreading activation.
#   Created: v0.2.0 — Implements Anderson's ACT-R power-law decay,
#   spreading activation via token overlap, emotional boost from
#   somatic markers, and stochastic noise for natural variability.

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import TYPE_CHECKING

from soul_protocol.runtime.memory.personality_modulation import compute_personality_boost
from soul_protocol.runtime.memory.search import relevance_score
from soul_protocol.runtime.types import MemoryEntry, Personality, SomaticMarker

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.strategy import SearchStrategy


# ---------------------------------------------------------------------------
# ACT-R Parameters (tuned for conversational AI, not cognitive modeling)
# ---------------------------------------------------------------------------

# Decay exponent — higher = faster forgetting. ACT-R default is 0.5.
DECAY_RATE: float = 0.5

# Weight for each component in the final activation score
W_BASE: float = 1.0  # base-level activation (recency + frequency)
W_SPREAD: float = 2.0  # spreading activation (query relevance) — raised for BM25
W_EMOTION: float = 0.5  # emotional boost
NOISE_SCALE: float = 0.1  # stochastic noise magnitude


def base_level_activation(
    timestamps: list[datetime],
    now: datetime | None = None,
) -> float:
    """Compute ACT-R base-level activation from access history.

    Formula: B_i = ln(sum(t_j^(-d))) where t_j is seconds since each access
    and d is the decay rate.

    Memories accessed more often and more recently have higher activation.
    This naturally implements both recency and frequency effects.

    Args:
        timestamps: List of datetime objects when this memory was accessed.
        now: Current time (defaults to datetime.now()).

    Returns:
        Base-level activation value (can be negative for old/rare memories).
    """
    if not timestamps:
        return 0.0

    now = now or datetime.now()
    total = 0.0

    for ts in timestamps:
        seconds_ago = max(1.0, (now - ts).total_seconds())
        total += seconds_ago ** (-DECAY_RATE)

    if total <= 0:
        return 0.0

    return math.log(total)


def spreading_activation(
    query: str,
    content: str,
    strategy: SearchStrategy | None = None,
) -> float:
    """Compute spreading activation from query context.

    Uses the provided SearchStrategy for scoring, or falls back to
    token-overlap relevance scoring. In ACT-R terms, this is the
    associative strength between the query (source) and the memory (target).

    Args:
        query: The retrieval cue (search query).
        content: The memory content to score against.
        strategy: Optional pluggable scoring strategy (v0.2.2).

    Returns:
        Activation spread value (0.0 to 1.0).
    """
    if strategy is not None:
        return strategy.score(query, content)
    return relevance_score(query, content)


def emotional_boost(somatic: SomaticMarker | None) -> float:
    """Compute activation boost from emotional intensity.

    Emotional memories are more easily recalled (Damasio). Higher arousal
    = stronger memory trace. Extreme valence (positive or negative) also
    contributes.

    Args:
        somatic: The memory's somatic marker (or None).

    Returns:
        Emotional boost value (0.0 to ~1.0).
    """
    if somatic is None:
        return 0.0

    # Arousal is the primary driver — intense emotions stick
    arousal_component = somatic.arousal

    # Absolute valence also contributes (both very positive and very negative
    # are memorable — the "flashbulb memory" effect)
    valence_component = abs(somatic.valence) * 0.3

    return min(1.0, arousal_component + valence_component)


def compute_activation(
    entry: MemoryEntry,
    query: str,
    now: datetime | None = None,
    noise: bool = True,
    strategy: SearchStrategy | None = None,
    personality: Personality | None = None,
) -> float:
    """Compute total activation for a memory entry.

    Combines:
    1. Base-level activation (ACT-R recency + frequency decay)
    2. Spreading activation (query relevance)
    3. Emotional boost (somatic markers)
    4. Personality modulation (OCEAN trait-based boost) (v0.3.3)
    5. Stochastic noise (natural variability)

    Graceful degradation: entries with no access_timestamps fall back to
    importance-weighted token-overlap scoring.

    Args:
        entry: The memory entry to score.
        query: The retrieval cue.
        now: Current time (defaults to datetime.now()).
        noise: Whether to add stochastic noise (disable for deterministic tests).
        strategy: Optional pluggable scoring strategy for spreading activation (v0.2.2).
        personality: Optional OCEAN personality for trait-modulated recall (v0.3.3).
            When None or all-0.5, no modulation is applied.

    Returns:
        Total activation score (higher = more likely to be recalled).
    """
    now = now or datetime.now()

    # Base-level: if we have access history, use ACT-R decay
    if entry.access_timestamps:
        base = base_level_activation(entry.access_timestamps, now)
    else:
        # Fallback: use importance as a proxy for base activation
        # Scale importance (1-10) to roughly match ACT-R range
        base = (entry.importance - 5) * 0.2  # maps 1-10 to -0.8 to 1.0

    # Spreading activation from query (uses pluggable strategy if provided)
    spread = spreading_activation(query, entry.content, strategy=strategy)

    # Emotional boost
    emo = emotional_boost(entry.somatic)

    # Importance boost: memories that passed a high significance bar get recall priority
    sig_boost = 0.3 * entry.significance if entry.significance else 0.0

    # Salience boost (v0.3.4-fix): additive instead of multiplicative.
    # Multiplicative salience amplified negative base (importance < 5), making
    # high-salience memories score WORSE — the opposite of intent.
    # Additive boost: high salience always helps, low salience is neutral.
    # Range: salience 0.0 → -0.25, salience 0.5 → 0.0, salience 1.0 → +0.25
    salience_boost = (entry.salience - 0.5) * 0.5

    # Personality modulation (v0.3.3)
    personality_boost = compute_personality_boost(entry, personality)

    # Combine with weights
    activation = (
        (W_BASE * base)
        + (W_SPREAD * spread)
        + (W_EMOTION * emo)
        + sig_boost
        + salience_boost
        + personality_boost
    )

    # Add stochastic noise for natural variability
    if noise:
        activation += random.gauss(0, NOISE_SCALE)

    return activation
