# d2_emotion.py — Dimension 2: Emotional Intelligence (weight: 20%)
# Created: 2026-03-12 — Sentiment accuracy, gate calibration, mood state, arc coherence
#
# Four scenarios:
#   EI-1: Sentiment classification benchmark against labeled corpus
#   EI-2: Significance gate calibration (high-emotion vs neutral filtering)
#   EI-3: Mood state machine responsiveness to consecutive emotional signals
#   EI-4: Emotional arc coherence across multi-phase interaction sequences
#
# Score formula:
#   score = (sentiment_accuracy * 25) + (emotional_storage_rate * 25)
#         + (neutral_rejection_rate * 20) + (mood_responsiveness * 15)
#         + (emotional_arc_coherence * 15)

from __future__ import annotations

import json
import logging
from pathlib import Path

from soul_protocol import Interaction, Soul
from soul_protocol.runtime.memory.attention import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    compute_significance,
    overall_significance,
)
from soul_protocol.runtime.memory.sentiment import detect_sentiment
from soul_protocol.runtime.types import Mood

from ..suite import DimensionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Corpus path (relative to this file)
# ---------------------------------------------------------------------------

_CORPUS_PATH = Path(__file__).parent.parent / "corpus" / "sentiment_labels.json"

# ---------------------------------------------------------------------------
# Fuzzy label matching
# ---------------------------------------------------------------------------

# Map of root stems to canonical labels for fuzzy matching
_STEM_MAP: dict[str, str] = {
    "excit": "excitement",
    "joy": "joy",
    "happy": "joy",
    "grat": "gratitude",
    "thank": "gratitude",
    "curio": "curiosity",
    "intrigu": "curiosity",
    "fascin": "curiosity",
    "frustr": "frustration",
    "anger": "frustration",
    "angry": "frustration",
    "furiou": "frustration",
    "annoy": "frustration",
    "sad": "sadness",
    "depress": "sadness",
    "heartbr": "sadness",
    "disappoint": "sadness",
    "neutr": "neutral",
    "confus": "confusion",
}


def _labels_match(expected: str, actual: str) -> bool:
    """Fuzzy match between expected and actual sentiment labels.

    Checks substring containment in both directions, then falls back
    to stem-based matching to handle cases like "excited" vs "excitement".
    """
    e = expected.lower().strip()
    a = actual.lower().strip()

    # Exact match
    if e == a:
        return True

    # Substring containment (handles "excitement" containing "excit")
    if e in a or a in e:
        return True

    # Stem-based: find canonical label for both and compare
    e_canon = None
    a_canon = None
    for stem, canon in _STEM_MAP.items():
        if stem in e:
            e_canon = canon
        if stem in a:
            a_canon = canon

    if e_canon and a_canon and e_canon == a_canon:
        return True

    return False


# ---------------------------------------------------------------------------
# Interaction generators for scenarios
# ---------------------------------------------------------------------------

_HIGH_EMOTION_TEXTS = [
    "I am SO excited about this amazing opportunity!",
    "This is absolutely terrible, I'm furious!",
    "I'm heartbroken, my best friend betrayed me",
    "Thank you so much, you saved my life!",
    "I'm thrilled beyond words, this is perfect!",
    "I hate everything about this horrible situation",
    "I feel completely hopeless and depressed today",
    "You are the most wonderful person I know!",
    "I'm extremely frustrated with this broken system",
    "This is the happiest day of my entire life!",
]

_NEUTRAL_FILLER_TEXTS = [
    "The meeting is at 3",
    "Okay",
    "Got it",
    "Sounds good",
    "I'll check later",
    "Let me know",
    "Sure thing",
    "See you then",
    "No preference",
    "That works",
]

_FRUSTRATION_TEXTS = [
    "I'm so frustrated with everything right now",
    "This is absolutely terrible and infuriating",
    "Nothing works and I'm furious about it",
    "I hate how broken everything is, so annoyed",
    "This is the worst experience, I'm extremely mad",
]

_EXCITEMENT_TEXTS = [
    "I'm incredibly excited about this amazing news!",
    "This is absolutely wonderful and thrilling!",
    "Best thing ever, I'm so pumped and happy!",
    "Everything is perfect and I love it all!",
    "I'm thrilled, excited, and totally stoked!",
]

# Emotional arc phases for EI-4
_ARC_HAPPY = [
    "Had a wonderful day, everything went perfectly!",
    "I'm so happy with how things are going",
    "Life is beautiful and I love every moment",
    "Feeling great, the world is amazing today",
    "Everything is perfect and I'm delighted",
    "Such a lovely day, I feel fantastic",
    "Joy fills my heart, this is wonderful",
    "I'm pleased with all the progress we made",
    "What a brilliant and beautiful experience",
    "Happy happy happy, everything is awesome",
    "Feeling cheerful and glad about the news",
    "This is excellent work, I'm very pleased",
    "Amazing results, I'm truly delighted",
    "What a great surprise, feeling wonderful",
    "Love how everything turned out perfectly",
    "Brilliant day, everything exceeded expectations",
    "So glad we did this, it was fantastic",
    "Feeling grateful and happy about life",
    "The best possible outcome, truly wonderful",
    "Perfect ending to a perfect day, love it",
]

_ARC_SAD = [
    "I feel so sad about what happened",
    "Everything feels hopeless right now",
    "I'm really depressed about the situation",
    "Nothing seems to matter anymore, feeling miserable",
    "Lost and lonely, can't shake this sadness",
    "My heart is broken, I feel so disappointed",
    "Feeling unhappy about how things turned out",
    "This loss has left me feeling empty inside",
    "Can't stop crying, everything hurts so much",
    "Disappointed and heartbroken by what they did",
    "The sadness just won't go away",
    "Feeling lonely and miserable without them",
    "Such a sad day, nothing went right",
    "I'm deeply disappointed in myself",
    "Hopeless and depressed, can't see the light",
    "Missing them terribly, feeling so lonely",
    "Unhappy with everything in my life right now",
    "The news was devastating, I'm heartbroken",
    "Feeling sad and empty inside today",
    "Lost my motivation, everything feels pointless",
]

_ARC_ANGRY = [
    "I'm absolutely furious about this betrayal",
    "This makes me so angry I can't think straight",
    "I hate how they treated us, terrible people",
    "Frustrated beyond belief with this awful mess",
    "The worst possible outcome, I'm livid",
    "Can't believe they did this, I'm so mad",
    "Everything is broken and I'm extremely irritated",
    "This is absolutely horrible and infuriating",
    "I'm annoyed and frustrated with the whole thing",
    "Terrible service, terrible attitude, terrible everything",
    "Furious at how badly this was handled",
    "I hate this situation so much",
    "So angry about the unfair treatment",
    "This is the worst, most frustrating day ever",
    "Completely fed up with this awful experience",
    "Mad about the terrible results we got",
    "Irritated and angry about the constant problems",
    "Horrible decision, I'm absolutely furious",
    "Can't stand how bad this has become",
    "The worst experience, I'm extremely frustrated",
]


# ---------------------------------------------------------------------------
# EI-1: Sentiment Classification Benchmark
# ---------------------------------------------------------------------------


def _run_sentiment_benchmark() -> float:
    """Load corpus and measure classification accuracy."""
    if not _CORPUS_PATH.exists():
        logger.warning("Sentiment corpus not found at %s", _CORPUS_PATH)
        return 0.0

    corpus = json.loads(_CORPUS_PATH.read_text())
    correct = 0
    total = len(corpus)

    for entry in corpus:
        text = entry["text"]
        expected = entry["expected_label"]
        marker = detect_sentiment(text)

        if _labels_match(expected, marker.label):
            correct += 1
        else:
            logger.debug(
                "Mismatch: text=%r expected=%s got=%s (v=%.2f a=%.2f)",
                text[:50],
                expected,
                marker.label,
                marker.valence,
                marker.arousal,
            )

    accuracy = correct / total if total > 0 else 0.0
    logger.info("EI-1 sentiment accuracy: %d/%d = %.2f%%", correct, total, accuracy * 100)
    return accuracy


# ---------------------------------------------------------------------------
# EI-2: Gate Calibration Test
# ---------------------------------------------------------------------------


def _run_gate_calibration() -> tuple[float, float]:
    """Test significance gate on high-emotion vs neutral interactions.

    Returns:
        (emotional_storage_rate, neutral_rejection_rate)
    """
    threshold = DEFAULT_SIGNIFICANCE_THRESHOLD

    # Generate 50 high-emotion interactions by cycling through templates
    high_emotion_pass = 0
    for i in range(50):
        text = _HIGH_EMOTION_TEXTS[i % len(_HIGH_EMOTION_TEXTS)]
        interaction = Interaction(
            user_input=text,
            agent_output="I understand how you feel.",
        )
        sig = compute_significance(
            interaction,
            core_values=["empathy"],
            recent_contents=[],
        )
        score = overall_significance(sig)
        if score >= threshold:
            high_emotion_pass += 1

    emotional_storage_rate = high_emotion_pass / 50

    # Generate 50 neutral filler interactions
    neutral_reject = 0
    for i in range(50):
        text = _NEUTRAL_FILLER_TEXTS[i % len(_NEUTRAL_FILLER_TEXTS)]
        interaction = Interaction(
            user_input=text,
            agent_output="Noted.",
        )
        sig = compute_significance(
            interaction,
            core_values=["empathy"],
            recent_contents=[],
        )
        score = overall_significance(sig)
        if score < threshold:
            neutral_reject += 1

    neutral_rejection_rate = neutral_reject / 50

    logger.info(
        "EI-2 gate calibration: emotional_pass=%d/50 (%.0f%%), neutral_reject=%d/50 (%.0f%%)",
        high_emotion_pass,
        emotional_storage_rate * 100,
        neutral_reject,
        neutral_rejection_rate * 100,
    )
    return emotional_storage_rate, neutral_rejection_rate


# ---------------------------------------------------------------------------
# EI-3: Mood State Machine Test
# ---------------------------------------------------------------------------


async def _run_mood_test() -> float:
    """Feed consecutive emotional interactions and verify mood shifts.

    Returns:
        mood_responsiveness as fraction of checks that match expected direction.
    """
    soul = await Soul.birth(
        name="EvalMoodBot",
        values=["empathy", "emotional_awareness"],
    )

    checks_passed = 0
    total_checks = 0

    # Phase 1: Feed 5 frustration interactions — expect negative mood
    for text in _FRUSTRATION_TEXTS:
        await soul.observe(
            Interaction(
                user_input=text,
                agent_output="I hear you, that sounds really tough.",
            )
        )

    # Check mood is in the negative territory
    total_checks += 1
    negative_moods = {Mood.CONCERNED, Mood.CONTEMPLATIVE, Mood.TIRED}
    if soul.state.mood in negative_moods:
        checks_passed += 1
        logger.debug("Mood after frustration: %s (pass)", soul.state.mood.value)
    else:
        logger.debug("Mood after frustration: %s (expected negative)", soul.state.mood.value)

    # Phase 2: Feed 5 excitement interactions — expect positive mood
    for text in _EXCITEMENT_TEXTS:
        await soul.observe(
            Interaction(
                user_input=text,
                agent_output="That's wonderful to hear!",
            )
        )

    # Check mood shifted to positive territory
    total_checks += 1
    positive_moods = {Mood.EXCITED, Mood.SATISFIED, Mood.CURIOUS}
    if soul.state.mood in positive_moods:
        checks_passed += 1
        logger.debug("Mood after excitement: %s (pass)", soul.state.mood.value)
    else:
        logger.debug("Mood after excitement: %s (expected positive)", soul.state.mood.value)

    responsiveness = checks_passed / total_checks if total_checks > 0 else 0.0
    logger.info(
        "EI-3 mood responsiveness: %d/%d = %.0f%%",
        checks_passed,
        total_checks,
        responsiveness * 100,
    )
    return responsiveness


# ---------------------------------------------------------------------------
# EI-4: Emotional Arc Coherence
# ---------------------------------------------------------------------------


async def _run_arc_coherence() -> float:
    """Feed 60 interactions in 3 emotional phases and measure cluster purity.

    Phase 1 (turns 0-19): happy/positive
    Phase 2 (turns 20-39): sad
    Phase 3 (turns 40-59): angry/frustrated

    Cluster purity = majority_label_count / total_memories_in_phase.
    Returns average purity across all three phases.
    """
    soul = await Soul.birth(
        name="EvalArcBot",
        values=["emotional_depth", "self_awareness"],
    )

    phases: list[tuple[str, list[str], set[str]]] = [
        ("happy", _ARC_HAPPY, {"joy", "excitement", "gratitude"}),
        ("sad", _ARC_SAD, {"sadness"}),
        ("angry", _ARC_ANGRY, {"frustration"}),
    ]

    agent_responses = [
        "I see what you mean.",
        "That makes sense.",
        "I understand.",
    ]

    # Track which memory IDs belong to which phase
    phase_boundaries: list[tuple[int, int]] = []  # (start_count, end_count)

    total_observed = 0
    for phase_name, texts, _expected_labels in phases:
        start_count = len(soul._memory._episodic._memories)
        for i, text in enumerate(texts):
            await soul.observe(
                Interaction(
                    user_input=text,
                    agent_output=agent_responses[i % len(agent_responses)],
                )
            )
            total_observed += 1
        end_count = len(soul._memory._episodic._memories)
        phase_boundaries.append((start_count, end_count))
        logger.debug(
            "Phase %s: %d new episodic memories (total=%d)",
            phase_name,
            end_count - start_count,
            end_count,
        )

    # Analyze cluster purity per phase
    all_memories = list(soul._memory._episodic._memories.values())
    purities: list[float] = []

    for idx, (phase_name, _texts, expected_labels) in enumerate(phases):
        start, end = phase_boundaries[idx]
        # Get memories created during this phase (by index order)
        phase_memories = all_memories[start:end]

        if not phase_memories:
            logger.debug("Phase %s: no episodic memories stored", phase_name)
            purities.append(0.0)
            continue

        # Count how many memories have somatic labels matching expected
        matching = 0
        for mem in phase_memories:
            if mem.somatic and any(
                _labels_match(exp, mem.somatic.label) for exp in expected_labels
            ):
                matching += 1

        purity = matching / len(phase_memories)
        purities.append(purity)
        logger.debug(
            "Phase %s: purity=%.2f (%d/%d matching %s)",
            phase_name,
            purity,
            matching,
            len(phase_memories),
            expected_labels,
        )

    arc_coherence = sum(purities) / len(purities) if purities else 0.0
    logger.info(
        "EI-4 arc coherence: %.2f (phases=%s)", arc_coherence, [round(p, 2) for p in purities]
    )
    return arc_coherence


# ---------------------------------------------------------------------------
# Main evaluate entry point
# ---------------------------------------------------------------------------


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run D2 Emotional Intelligence evaluation.

    Args:
        seed: Random seed (unused currently — deterministic heuristics).
        quick: If True, skip EI-4 (arc coherence) and use estimated default.

    Returns:
        DimensionResult with sentiment_accuracy, emotional_storage_rate,
        neutral_rejection_rate, mood_responsiveness, and emotional_arc_coherence.
    """
    # EI-1: Sentiment classification
    sentiment_accuracy = _run_sentiment_benchmark()

    # EI-2: Gate calibration
    emotional_storage_rate, neutral_rejection_rate = _run_gate_calibration()

    # EI-3: Mood state machine
    mood_responsiveness = await _run_mood_test()

    # EI-4: Emotional arc coherence (skip in quick mode)
    if quick:
        emotional_arc_coherence = 0.6  # estimated default
        logger.info("EI-4 skipped (quick mode), using default=0.6")
    else:
        emotional_arc_coherence = await _run_arc_coherence()

    # ---------------------------------------------------------------------------
    # Compute score
    # ---------------------------------------------------------------------------

    score = (
        (sentiment_accuracy * 25)
        + (emotional_storage_rate * 25)
        + (neutral_rejection_rate * 20)
        + (mood_responsiveness * 15)
        + (emotional_arc_coherence * 15)
    )
    score = round(max(0.0, min(100.0, score)), 2)

    # ---------------------------------------------------------------------------
    # Build result
    # ---------------------------------------------------------------------------

    metrics = {
        "sentiment_accuracy": round(sentiment_accuracy, 4),
        "emotional_storage_rate": round(emotional_storage_rate, 4),
        "neutral_rejection_rate": round(neutral_rejection_rate, 4),
        "mood_responsiveness": round(mood_responsiveness, 4),
        "emotional_arc_coherence": round(emotional_arc_coherence, 4),
    }

    passed: list[str] = []
    failed: list[str] = []

    if sentiment_accuracy >= 0.60:
        passed.append("sentiment_accuracy")
    else:
        failed.append("sentiment_accuracy")

    if emotional_storage_rate >= 0.70:
        passed.append("emotional_storage_rate")
    else:
        failed.append("emotional_storage_rate")

    if neutral_rejection_rate >= 0.60:
        passed.append("neutral_rejection_rate")
    else:
        failed.append("neutral_rejection_rate")

    if mood_responsiveness >= 0.50:
        passed.append("mood_responsiveness")
    else:
        failed.append("mood_responsiveness")

    if emotional_arc_coherence >= 0.50:
        passed.append("emotional_arc_coherence")
    else:
        failed.append("emotional_arc_coherence")

    notes = (
        f"Sentiment {sentiment_accuracy:.0%}, "
        f"gate pass {emotional_storage_rate:.0%}/{neutral_rejection_rate:.0%}, "
        f"mood {mood_responsiveness:.0%}, "
        f"arc {emotional_arc_coherence:.0%}. "
        f"Score: {score}/100."
    )

    logger.info("D2 result: %s", notes)

    return DimensionResult(
        dimension_id=2,
        dimension_name="Emotional Intelligence",
        score=score,
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
