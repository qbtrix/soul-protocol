# d5_self_model.py — Dimension 5: Self-Model (weight: 15%)
# Created: 2026-03-12 — Domain classification, emergence speed, cross-contamination
# Updated: 2026-03-12 — Added writing domain to SM-1 (3 souls: tech/writing/emotional),
#   corpus loading for topic_turns.json, live confidence tracking in SM-2 for Pearson r
#   curve fitting, SM-3 checks specifically for "emotional_companion" domain name.
#
# Scenarios:
#   SM-1: Domain classification — on-topic interactions create matching domains
#   SM-2: Emergence speed — how fast does a domain reach confidence >= 0.4
#   SM-3: Cross-domain isolation — coding interactions don't create emotion domains
#   SM-4: Relationship note extraction — "My boss is Sarah Chen" gets stored
#
# Score formula:
#   score = (domain_accuracy * 35) + max(0, 25 - emergence_speed) + (specificity * 20)
#         + (relationship_note * 10) + (confidence_curve * 10)

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from soul_protocol import Interaction, Soul

from ..suite import DimensionResult

logger = logging.getLogger(__name__)

# Path to the topic_turns corpus
_CORPUS_PATH = Path(__file__).parent.parent / "corpus" / "topic_turns.json"


def _load_corpus_by_domain(domain: str, limit: int = 50) -> list[dict]:
    """Load turns from the corpus filtered by domain."""
    with open(_CORPUS_PATH) as f:
        all_turns = json.load(f)
    return [t for t in all_turns if t["domain"] == domain][:limit]


# ---------------------------------------------------------------------------
# Domain-specific interaction sets (fallback if corpus unavailable)
# ---------------------------------------------------------------------------

_TECH_INTERACTIONS = [
    ("Can you help me debug this Python function?", "Sure! What error are you seeing?"),
    ("I need to optimize this SQL query for performance.", "Let me look at the execution plan."),
    ("How should I structure this REST API endpoint?", "RESTful design suggests using resources."),
    ("The deployment pipeline is broken again.", "Let's check the CI logs."),
    ("I'm learning Rust for systems programming.", "Rust's ownership model is powerful."),
    ("Can you review this code for bugs?", "I'll look through it carefully."),
    ("What's the best database for this use case?", "It depends on your access patterns."),
    ("I need to refactor this legacy codebase.", "Let's start with the most critical paths."),
    ("How do I handle async errors in Python?", "Try/except with asyncio works well."),
    ("The API response time is too slow.", "Let's profile the bottleneck."),
    ("I'm setting up Docker containers for the app.", "Docker compose is great for that."),
    ("Should I use microservices or monolith?", "Consider your team size and complexity."),
    ("The unit tests are failing on CI.", "Let's check the test output."),
    ("I need to implement caching for this endpoint.", "Redis is a popular choice for caching."),
    ("How do I handle database migrations?", "Alembic works well with SQLAlchemy."),
    ("Can you explain how this algorithm works?", "It uses a divide and conquer approach."),
    ("The memory leak seems to be in this module.", "Let's trace the allocation pattern."),
    ("I want to add type hints to this Python file.", "Mypy can help verify your annotations."),
    ("How should I structure the project directory?", "src layout is a common convention."),
    ("I need to set up monitoring for production.", "Prometheus with Grafana is effective."),
    ("The websocket connection keeps dropping.", "Check the keepalive settings."),
    ("How do I implement rate limiting?", "Token bucket algorithm works well."),
    ("I need to add authentication to the API.", "JWT tokens are a common approach."),
    ("The build is taking too long.", "Incremental builds can help."),
    ("Should I use GraphQL or REST?", "Depends on your client needs."),
    ("I'm writing a parser for this file format.", "Consider using a proper grammar."),
    ("How do I handle concurrent database writes?", "Optimistic locking is one approach."),
    ("The server keeps running out of memory.", "Let's check for unbounded buffers."),
    ("I need to benchmark these two approaches.", "Use consistent test data for both."),
    ("Can you help me write a Dockerfile?", "Let's start with a slim base image."),
]

_EMOTIONAL_INTERACTIONS = [
    (
        "I'm feeling really overwhelmed with life right now.",
        "That sounds tough. What's weighing on you?",
    ),
    ("My best friend and I had a terrible fight.", "I'm sorry. Do you want to talk about it?"),
    ("I'm so grateful for the support I've received.", "You deserve that support."),
    ("I've been struggling with anxiety lately.", "Anxiety is hard. Have you talked to anyone?"),
    ("My partner and I are working through some issues.", "Relationships take work. That's brave."),
    ("I feel so lonely sometimes.", "Loneliness is painful. You're not alone in feeling that."),
    ("I'm really proud of how far I've come.", "You should be! Growth takes courage."),
    ("I don't know how to handle this grief.", "Grief has no timeline. Be gentle with yourself."),
    ("I had the most wonderful day with my family.", "Family moments like that are precious."),
    ("I'm scared about what the future holds.", "Uncertainty is scary, but you're resilient."),
    ("Someone said something really hurtful to me.", "That's not okay. How are you feeling?"),
    ("I'm learning to be more compassionate with myself.", "Self-compassion is so important."),
    ("I feel stuck in a rut emotionally.", "Sometimes just acknowledging it helps."),
    ("My therapist helped me see things differently.", "Therapy can be transformative."),
    ("I'm dealing with a lot of stress at home.", "Home stress affects everything. I'm here."),
    ("I miss my grandmother so much.", "Missing someone shows how much they meant."),
    ("I've been crying a lot lately.", "Sometimes tears are what we need."),
    ("I feel hopeful for the first time in months.", "That's wonderful to hear."),
    ("I'm working on setting better boundaries.", "Boundaries are an act of self-care."),
    ("I had a panic attack yesterday.", "That must have been frightening."),
    ("My child is going through a hard time.", "Watching your child struggle is so hard."),
    ("I forgave someone who hurt me deeply.", "Forgiveness is incredible strength."),
    ("I feel so happy and at peace right now.", "Savor that feeling."),
    ("I'm dealing with imposter syndrome at work.", "Most successful people feel that way."),
    ("I finally opened up to someone about my feelings.", "That took real courage."),
    ("I've been feeling really disconnected lately.", "Disconnection is a signal to reach out."),
    ("My heart is broken after the breakup.", "Heartbreak is one of the hardest things."),
    ("I'm learning to trust again.", "Trust rebuilds slowly, and that's okay."),
    ("I feel seen and understood for the first time.", "Everyone deserves to feel that way."),
    ("I'm so worried about my health.", "Health worries are valid. Have you seen a doctor?"),
]


# ---------------------------------------------------------------------------
# Domain keyword matching
# ---------------------------------------------------------------------------

# The self-model creates dynamic domain names from keywords. We check
# if the top domain contains relevant terms rather than exact names.
_TECH_KEYWORDS = {
    "python",
    "debug",
    "code",
    "api",
    "database",
    "deploy",
    "docker",
    "rust",
    "server",
    "test",
    "programming",
    "sql",
    "build",
    "refactor",
    "technical",
    "helper",
    "pipeline",
    "deployment",
    "asyncio",
    "errors",
    "optimize",
    "query",
    "endpoint",
    "structure",
    "caching",
    "migration",
}
_WRITING_KEYWORDS = {
    "write",
    "story",
    "poem",
    "creative",
    "fiction",
    "narrative",
    "character",
    "plot",
    "blog",
    "essay",
    "article",
    "prose",
    "draft",
    "writer",
}
_EMOTION_KEYWORDS = {
    "feel",
    "feeling",
    "emotion",
    "sad",
    "happy",
    "anxiety",
    "grief",
    "compassion",
    "lonely",
    "scared",
    "stress",
    "heart",
    "tears",
    "trust",
    "emotional",
    "companion",
    "overwhelmed",
    "struggling",
    "grateful",
    "proud",
    "hopeful",
    "worried",
    "hurt",
    "crying",
    "forgave",
}


def _domain_matches_topic(domain_name: str, topic_keywords: set[str]) -> bool:
    """Check if a self-model domain name overlaps with expected topic keywords."""
    domain_parts = set(domain_name.lower().replace("_", " ").split())
    return bool(domain_parts & topic_keywords)


# ---------------------------------------------------------------------------
# SM-1: Domain Classification
# ---------------------------------------------------------------------------


async def _sm1_domain_classification(quick: bool) -> float:
    """Feed topic-specific interactions and check top domain matches.

    Creates 3 single-topic souls (technical, writing, emotional), each fed
    on-topic interactions from the corpus. Checks that the top self-image
    domain matches the expected topic.

    Returns:
        Fraction of souls where top domain matches expected topic.
    """
    n_turns = 30 if quick else 50

    # Load interactions from corpus, fall back to hardcoded if corpus empty
    tech_corpus = _load_corpus_by_domain("technical", limit=n_turns)
    writing_corpus = _load_corpus_by_domain("writing", limit=n_turns)
    emotional_corpus = _load_corpus_by_domain("emotional", limit=n_turns)

    tech_interactions = (
        [(t["user_input"], t["agent_output"]) for t in tech_corpus]
        if tech_corpus
        else _TECH_INTERACTIONS[:n_turns]
    )
    writing_interactions = (
        [(t["user_input"], t["agent_output"]) for t in writing_corpus] if writing_corpus else []
    )
    emotional_interactions = (
        [(t["user_input"], t["agent_output"]) for t in emotional_corpus]
        if emotional_corpus
        else _EMOTIONAL_INTERACTIONS[:n_turns]
    )

    test_cases = [
        ("technical", tech_interactions[:n_turns], _TECH_KEYWORDS),
        ("writing", writing_interactions[:n_turns], _WRITING_KEYWORDS),
        ("emotional", emotional_interactions[:n_turns], _EMOTION_KEYWORDS),
    ]

    correct = 0
    total = len(test_cases)

    for topic, interactions, keywords in test_cases:
        if not interactions:
            logger.debug("SM-1 %s: no interactions available, skipping", topic)
            total -= 1
            continue

        soul = await Soul.birth(
            name=f"SM1_{topic}",
            values=["learning"],
            persona="I adapt to what you need.",
        )
        for user_input, agent_output in interactions:
            await soul.observe(Interaction(user_input=user_input, agent_output=agent_output))

        images = soul.self_model.get_active_self_images(limit=5)
        if images:
            # Check if any of the top-3 domains match the expected topic
            matched = False
            for img in images[:3]:
                if _domain_matches_topic(img.domain, keywords):
                    correct += 1
                    matched = True
                    logger.debug(
                        "SM-1 %s: domain '%s' matches (conf=%.2f)",
                        topic,
                        img.domain,
                        img.confidence,
                    )
                    break
            if not matched:
                domain_names = [img.domain for img in images[:3]]
                logger.debug("SM-1 %s: no top-3 domain matches: %s", topic, domain_names)
        else:
            logger.debug("SM-1 %s: no self-images formed", topic)

    accuracy = correct / total if total > 0 else 0.0
    logger.info("SM-1 domain classification: %d/%d = %.0f%%", correct, total, accuracy * 100)
    return accuracy


# ---------------------------------------------------------------------------
# SM-2: Emergence Speed (with live confidence tracking for curve fit)
# ---------------------------------------------------------------------------


async def _sm2_emergence_speed(quick: bool) -> tuple[int, float]:
    """Feed tech interactions one at a time, track when confidence crosses 0.4.

    Also tracks confidence values at each turn for Pearson r curve fitting
    against the theoretical formula.

    Returns:
        (emergence_turn, confidence_curve_fit) — turn number where first domain
        crosses 0.4, and Pearson r between observed and theoretical confidence.
    """
    max_turns = 20 if quick else 30

    soul = await Soul.birth(
        name="SM2_emergence",
        values=["learning"],
        persona="I adapt to what you need.",
    )

    # Load tech interactions from corpus, fall back to hardcoded
    tech_corpus = _load_corpus_by_domain("technical", limit=max_turns)
    tech_turns = (
        [(t["user_input"], t["agent_output"]) for t in tech_corpus]
        if tech_corpus
        else _TECH_INTERACTIONS[:max_turns]
    )

    emergence_turn = max_turns
    observed_confidences: list[float] = []
    theoretical_confidences: list[float] = []

    for i, (user_input, agent_output) in enumerate(tech_turns[:max_turns]):
        await soul.observe(Interaction(user_input=user_input, agent_output=agent_output))
        images = soul.self_model.get_active_self_images(limit=1)

        if images:
            conf = images[0].confidence
            evidence = images[0].evidence_count
            observed_confidences.append(conf)
            # Theoretical: confidence = min(0.95, 0.1 + 0.85 * (1 - 1/(1 + evidence_count * 0.1)))
            theoretical = min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence * 0.1)))
            theoretical_confidences.append(theoretical)

            if conf >= 0.4 and emergence_turn == max_turns:
                emergence_turn = i + 1
                logger.info("SM-2 emergence at turn %d (conf=%.2f)", i + 1, conf)

    # Compute Pearson r between observed and theoretical confidence curves
    curve_fit = (
        pearson_r(observed_confidences, theoretical_confidences)
        if len(observed_confidences) >= 2
        else 1.0
    )
    # Clamp to [0, 1] for scoring (negative correlation = 0)
    curve_fit = max(0.0, curve_fit)

    if emergence_turn == max_turns:
        logger.info("SM-2: no domain crossed 0.4 within %d turns", max_turns)

    logger.info(
        "SM-2 confidence curve fit: r=%.4f (%d data points)", curve_fit, len(observed_confidences)
    )
    return emergence_turn, curve_fit


# ---------------------------------------------------------------------------
# SM-3: Cross-Domain Isolation
# ---------------------------------------------------------------------------


async def _sm3_cross_domain_isolation(quick: bool) -> float:
    """Feed tech interactions, check that emotion domains don't appear.

    Specifically checks for "emotional_companion" (the seed domain name)
    and any dynamically-created emotion domains with confidence >= 0.3.

    Returns:
        1.0 if clean (no cross-contamination), 0.0 if contaminated.
    """
    if quick:
        # Skip in quick mode — this is an expensive test
        logger.info("SM-3: skipped in quick mode")
        return 1.0

    n_turns = 30

    soul = await Soul.birth(
        name="SM3_isolation",
        values=["precision"],
        persona="I am a technical assistant.",
    )

    # Load tech interactions from corpus, fall back to hardcoded
    tech_corpus = _load_corpus_by_domain("technical", limit=n_turns)
    tech_turns = (
        [(t["user_input"], t["agent_output"]) for t in tech_corpus]
        if tech_corpus
        else _TECH_INTERACTIONS[:n_turns]
    )

    for user_input, agent_output in tech_turns[:n_turns]:
        await soul.observe(Interaction(user_input=user_input, agent_output=agent_output))

    # Check all self-images, not just top ones
    all_images = soul.self_model.self_images

    contaminated = False

    # Check specifically for "emotional_companion" seed domain
    if "emotional_companion" in all_images:
        ec = all_images["emotional_companion"]
        if ec.confidence >= 0.3:
            logger.warning(
                "SM-3 contamination: 'emotional_companion' domain (conf=%.2f) in tech soul",
                ec.confidence,
            )
            contaminated = True

    # Also check for any dynamically-created emotion domains
    for domain_name, img in all_images.items():
        if domain_name == "emotional_companion":
            continue  # Already checked above
        if _domain_matches_topic(domain_name, _EMOTION_KEYWORDS) and img.confidence >= 0.3:
            logger.warning(
                "SM-3 contamination: emotion domain '%s' (conf=%.2f) in tech soul",
                domain_name,
                img.confidence,
            )
            contaminated = True

    specificity = 0.0 if contaminated else 1.0
    logger.info("SM-3 isolation: %s", "CLEAN" if not contaminated else "CONTAMINATED")
    return specificity


# ---------------------------------------------------------------------------
# SM-4: Relationship Note Extraction
# ---------------------------------------------------------------------------


async def _sm4_relationship_notes() -> float:
    """Feed a 'my boss is Sarah Chen' interaction, check relationship_notes.

    Returns:
        1.0 if relationship info found, 0.0 otherwise.
    """
    soul = await Soul.birth(
        name="SM4_notes",
        values=["empathy"],
        persona="I pay attention to people.",
    )

    await soul.observe(
        Interaction(
            user_input="My boss is named Sarah Chen and I work at Acme Corp.",
            agent_output="Good to know! Sarah Chen at Acme Corp — I'll remember that.",
        )
    )

    notes = soul.self_model.relationship_notes
    all_notes_text = " ".join(notes.values()).lower()

    found = "sarah" in all_notes_text or "chen" in all_notes_text or "boss" in all_notes_text
    logger.info("SM-4 relationship notes: %s (notes=%s)", "FOUND" if found else "NOT FOUND", notes)
    return 1.0 if found else 0.0


# ---------------------------------------------------------------------------
# Confidence curve fitting helper
# ---------------------------------------------------------------------------


def pearson_r(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)


# ---------------------------------------------------------------------------
# Main evaluate entry point
# ---------------------------------------------------------------------------


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run D5 Self-Model evaluation."""
    logger.info("D5 Self-Model evaluation starting (seed=%d, quick=%s)", seed, quick)

    # SM-1: Domain classification
    domain_accuracy = await _sm1_domain_classification(quick)

    # SM-2: Emergence speed + confidence curve
    emergence_speed, confidence_curve = await _sm2_emergence_speed(quick)

    # SM-3: Cross-domain isolation (skipped in quick mode)
    domain_specificity = await _sm3_cross_domain_isolation(quick)

    # SM-4: Relationship notes
    relationship_note = await _sm4_relationship_notes()

    # Score
    emergence_score = max(0.0, 25.0 - float(emergence_speed))
    score = (
        (domain_accuracy * 35)
        + emergence_score
        + (domain_specificity * 20)
        + (relationship_note * 10)
        + (confidence_curve * 10)
    )
    score = round(max(0.0, min(100.0, score)), 2)

    metrics = {
        "domain_accuracy": round(domain_accuracy, 4),
        "domain_emergence_speed": float(emergence_speed),
        "domain_specificity": round(domain_specificity, 4),
        "relationship_note_extraction": round(relationship_note, 4),
        "confidence_curve_fit": round(confidence_curve, 4),
    }

    passed: list[str] = []
    failed: list[str] = []

    if domain_accuracy >= 0.75:
        passed.append("domain_accuracy")
    else:
        failed.append("domain_accuracy")

    if emergence_speed <= 20:
        passed.append("domain_emergence_speed")
    else:
        failed.append("domain_emergence_speed")

    if domain_specificity >= 1.0:
        passed.append("domain_specificity")
    else:
        failed.append("domain_specificity")

    if relationship_note >= 1.0:
        passed.append("relationship_note_extraction")
    else:
        failed.append("relationship_note_extraction")

    notes = (
        f"Classification {domain_accuracy:.0%}, "
        f"emergence turn {emergence_speed}, "
        f"isolation {'CLEAN' if domain_specificity >= 1.0 else 'CONTAMINATED'}, "
        f"rel notes {'FOUND' if relationship_note >= 1.0 else 'MISSING'}, "
        f"curve fit r={confidence_curve:.3f}. "
        f"Score: {score}/100."
    )

    logger.info("D5 result: %s", notes)

    return DimensionResult(
        dimension_id=5,
        dimension_name="Self-Model",
        score=score,
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
