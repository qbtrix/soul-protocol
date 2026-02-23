# test_self_model.py — Tests for Klein's self-concept model.
# Updated: 2026-02-23 — Updated for emergent domain discovery. Tests now cover:
#   - DEFAULT_SEED_DOMAINS import (renamed from DOMAIN_KEYWORDS)
#   - Emergent domain creation for novel content (cooking, fitness, etc.)
#   - Domain keyword growth over time
#   - seed_domains constructor parameter
#   - Serialization/deserialization of domain_keywords
#   - STOP_WORDS filtering
#   - All existing backward-compat assertions preserved

from __future__ import annotations

import pytest

from soul_protocol.memory.self_model import (
    DEFAULT_SEED_DOMAINS,
    DOMAIN_KEYWORDS,
    STOP_WORDS,
    SelfModelManager,
)
from soul_protocol.types import Interaction, MemoryEntry, MemoryType, SelfImage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interaction(user_input: str = "", agent_output: str = "") -> Interaction:
    """Build a minimal Interaction for testing."""
    return Interaction(user_input=user_input, agent_output=agent_output)


def _fact(content: str) -> MemoryEntry:
    """Build a semantic MemoryEntry with the given content."""
    return MemoryEntry(type=MemoryType.SEMANTIC, content=content)


def _expected_confidence(evidence_count: int) -> float:
    """The confidence formula used by SelfModelManager._update_domain."""
    return min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence_count * 0.1)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager() -> SelfModelManager:
    """Return a fresh SelfModelManager with default seed domains."""
    return SelfModelManager()


@pytest.fixture
def empty_manager() -> SelfModelManager:
    """Return a SelfModelManager with no seed domains at all."""
    return SelfModelManager(seed_domains={})


# ---------------------------------------------------------------------------
# 1. New manager starts empty
# ---------------------------------------------------------------------------

def test_new_manager_has_no_self_images(manager: SelfModelManager) -> None:
    """A freshly created SelfModelManager has no self-images."""
    assert manager.self_images == {}


def test_new_manager_has_no_relationship_notes(manager: SelfModelManager) -> None:
    """A freshly created SelfModelManager has no relationship notes."""
    assert manager.relationship_notes == {}


# ---------------------------------------------------------------------------
# 2. Technical interaction creates technical_helper self-image
# ---------------------------------------------------------------------------

def test_technical_interaction_creates_technical_helper(manager: SelfModelManager) -> None:
    """An interaction mentioning Python code should create a technical_helper self-image."""
    manager.update_from_interaction(
        _interaction("Help me write a python function", "Sure, here is the code"),
        [],
    )
    assert "technical_helper" in manager.self_images


def test_technical_helper_confidence_above_baseline(manager: SelfModelManager) -> None:
    """After a technical interaction, technical_helper confidence exceeds the initial 0.1 floor."""
    manager.update_from_interaction(
        _interaction("Debug my python code", "Found the error"),
        [],
    )
    img = manager.self_images["technical_helper"]
    assert img.confidence > 0.1


# ---------------------------------------------------------------------------
# 3. Evidence accumulates across multiple interactions
# ---------------------------------------------------------------------------

def test_evidence_accumulates_with_repeated_interactions(manager: SelfModelManager) -> None:
    """Each technical interaction increases evidence_count for technical_helper."""
    interaction = _interaction("Review this python code", "Looks good")
    manager.update_from_interaction(interaction, [])
    first_count = manager.self_images["technical_helper"].evidence_count

    manager.update_from_interaction(interaction, [])
    second_count = manager.self_images["technical_helper"].evidence_count

    assert second_count > first_count


def test_confidence_grows_with_more_interactions(manager: SelfModelManager) -> None:
    """More interactions with technical content should raise confidence monotonically."""
    interaction = _interaction("Explain this python algorithm", "Here is how it works")

    manager.update_from_interaction(interaction, [])
    first_confidence = manager.self_images["technical_helper"].confidence

    for _ in range(10):
        manager.update_from_interaction(interaction, [])

    later_confidence = manager.self_images["technical_helper"].confidence
    assert later_confidence > first_confidence


# ---------------------------------------------------------------------------
# 4. Multiple domains can coexist (via separate interactions)
# ---------------------------------------------------------------------------

def test_multiple_domains_coexist(manager: SelfModelManager) -> None:
    """Separate interactions targeting different domains create self-images for both."""
    # Emergent discovery matches one domain per interaction, so use two interactions
    manager.update_from_interaction(
        _interaction("Help me debug python code", "Here is the fix"),
        [],
    )
    manager.update_from_interaction(
        _interaction("Write a creative story", "Once upon a time..."),
        [],
    )
    images = manager.self_images
    assert "technical_helper" in images
    assert "creative_writer" in images
    assert len(images) >= 2


def test_distinct_interactions_build_separate_domains(manager: SelfModelManager) -> None:
    """Separate interactions targeting different domains each create their own self-image."""
    manager.update_from_interaction(
        _interaction("Help me debug this code", "Fixed it"), []
    )
    manager.update_from_interaction(
        _interaction("Write a short poem for me", "Roses are red..."), []
    )
    images = manager.self_images
    assert "technical_helper" in images
    assert "creative_writer" in images


# ---------------------------------------------------------------------------
# 5. get_active_self_images respects the limit
# ---------------------------------------------------------------------------

def test_get_active_self_images_respects_limit(manager: SelfModelManager) -> None:
    """get_active_self_images(limit=1) returns at most one result."""
    manager.update_from_interaction(
        _interaction("Debug my python code", "Fixed"), []
    )
    manager.update_from_interaction(
        _interaction("Write a creative story", "Once upon a time"), []
    )
    manager.update_from_interaction(
        _interaction("Explain this concept to me", "Sure"), []
    )
    active = manager.get_active_self_images(limit=1)
    assert len(active) == 1


def test_get_active_self_images_returns_at_most_limit(manager: SelfModelManager) -> None:
    """get_active_self_images with limit=2 returns no more than 2 images even with more domains."""
    interactions = [
        _interaction("python code debugging", "Fixed"),
        _interaction("write a creative story poem", "Once upon a time"),
        _interaction("explain the science concept", "Sure, the theory is"),
        _interaction("brainstorm new design ideas", "Let me think"),
    ]
    for i in interactions:
        manager.update_from_interaction(i, [])

    active = manager.get_active_self_images(limit=2)
    assert len(active) <= 2


# ---------------------------------------------------------------------------
# 6. get_active_self_images sorted by confidence (descending)
# ---------------------------------------------------------------------------

def test_get_active_self_images_sorted_by_confidence_descending(manager: SelfModelManager) -> None:
    """get_active_self_images returns images sorted highest confidence first."""
    # Build up technical_helper with many interactions so it has the highest confidence
    tech_interaction = _interaction("python code function algorithm", "Here is the solution")
    for _ in range(15):
        manager.update_from_interaction(tech_interaction, [])

    # One creative interaction gives creative_writer less evidence
    manager.update_from_interaction(
        _interaction("write a short story", "Once upon a time"), []
    )

    active = manager.get_active_self_images(limit=3)
    assert len(active) >= 2
    confidences = [img.confidence for img in active]
    assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# 7. to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

def test_to_dict_from_dict_round_trip_self_images(manager: SelfModelManager) -> None:
    """Serializing and deserializing preserves all self-image domain data."""
    manager.update_from_interaction(
        _interaction("I need help with python code", "Here is the fix"), []
    )
    original_images = manager.self_images

    restored = SelfModelManager.from_dict(manager.to_dict())

    assert set(restored.self_images.keys()) == set(original_images.keys())
    for domain, img in original_images.items():
        restored_img = restored.self_images[domain]
        assert restored_img.domain == img.domain
        assert restored_img.confidence == pytest.approx(img.confidence)
        assert restored_img.evidence_count == img.evidence_count


def test_to_dict_from_dict_round_trip_relationship_notes(manager: SelfModelManager) -> None:
    """Serializing and deserializing preserves relationship notes."""
    manager.update_from_interaction(
        _interaction("Hi", "Hello!"),
        [_fact("User's name is Elena")],
    )
    original_notes = manager.relationship_notes

    restored = SelfModelManager.from_dict(manager.to_dict())

    assert restored.relationship_notes == original_notes


def test_from_dict_empty_data_creates_empty_manager() -> None:
    """from_dict with an empty dict produces a manager with no images or notes."""
    manager = SelfModelManager.from_dict({})
    assert manager.self_images == {}
    assert manager.relationship_notes == {}


# ---------------------------------------------------------------------------
# 8. to_prompt_fragment with no images returns empty string
# ---------------------------------------------------------------------------

def test_prompt_fragment_empty_when_no_self_images(manager: SelfModelManager) -> None:
    """to_prompt_fragment returns an empty string when the soul has no self-images."""
    assert manager.to_prompt_fragment() == ""


# ---------------------------------------------------------------------------
# 9. to_prompt_fragment with images contains domain names
# ---------------------------------------------------------------------------

def test_prompt_fragment_contains_domain_name(manager: SelfModelManager) -> None:
    """to_prompt_fragment includes the active domain name in human-readable form."""
    manager.update_from_interaction(
        _interaction("Help debug my python code", "Fixed"), []
    )
    fragment = manager.to_prompt_fragment()
    # Domain "technical_helper" is rendered as "technical helper" (underscores → spaces)
    assert "technical helper" in fragment


def test_prompt_fragment_contains_self_understanding_header(manager: SelfModelManager) -> None:
    """to_prompt_fragment includes the ## Self-Understanding header when images exist."""
    manager.update_from_interaction(
        _interaction("Write a story for me", "Once upon a time"), []
    )
    fragment = manager.to_prompt_fragment()
    assert "## Self-Understanding" in fragment


def test_prompt_fragment_confidence_label_emerging_for_low_confidence(manager: SelfModelManager) -> None:
    """A domain with low evidence shows 'emerging' confidence label in the prompt."""
    # One interaction → evidence_count will be small → confidence < 0.4
    manager.update_from_interaction(
        _interaction("write a short poem", "Roses are red"), []
    )
    fragment = manager.to_prompt_fragment()
    assert "emerging" in fragment


# ---------------------------------------------------------------------------
# 10. relationship_notes extracted from facts
# ---------------------------------------------------------------------------

def test_relationship_notes_captures_user_name(manager: SelfModelManager) -> None:
    """A fact containing \"User's name is X\" is recorded in relationship_notes."""
    manager.update_from_interaction(
        _interaction("Hi", "Hello!"),
        [_fact("User's name is Marcus")],
    )
    assert "user" in manager.relationship_notes
    assert "Marcus" in manager.relationship_notes["user"]


def test_relationship_notes_captures_workplace(manager: SelfModelManager) -> None:
    """A fact containing \"User works at X\" is recorded in relationship_notes."""
    manager.update_from_interaction(
        _interaction("Hi", "Hello!"),
        [_fact("User works at Acme Corp")],
    )
    assert "user" in manager.relationship_notes
    assert "Acme Corp" in manager.relationship_notes["user"]


# ---------------------------------------------------------------------------
# 11. Confidence formula: many interactions → high confidence
# ---------------------------------------------------------------------------

def test_high_evidence_produces_high_confidence(manager: SelfModelManager) -> None:
    """After many technical interactions, technical_helper confidence exceeds 0.85."""
    interaction = _interaction("python code debug algorithm", "Here is the fix")
    # 50 iterations with 3+ keyword matches each → large evidence_count
    for _ in range(50):
        manager.update_from_interaction(interaction, [])

    img = manager.self_images["technical_helper"]
    assert img.confidence > 0.85


def test_confidence_never_exceeds_cap(manager: SelfModelManager) -> None:
    """No matter how many interactions occur, confidence is capped at 0.95."""
    interaction = _interaction("python code debug algorithm function class", "Done")
    for _ in range(500):
        manager.update_from_interaction(interaction, [])

    img = manager.self_images["technical_helper"]
    assert img.confidence <= 0.95


# ---------------------------------------------------------------------------
# 12. Confidence formula: few interactions → low confidence
# ---------------------------------------------------------------------------

def test_few_interactions_produce_low_confidence(manager: SelfModelManager) -> None:
    """After only one interaction, confidence for any domain stays below 0.4."""
    manager.update_from_interaction(
        _interaction("Help me with some python code", "Sure"), []
    )
    for img in manager.self_images.values():
        assert img.confidence < 0.4


def test_confidence_formula_matches_expected_value(manager: SelfModelManager) -> None:
    """The stored confidence exactly matches the formula for the accumulated evidence_count."""
    interaction = _interaction("python code debug", "Fixed")
    # Run a known number of times so we can compute expected evidence_count
    for _ in range(5):
        manager.update_from_interaction(interaction, [])

    img = manager.self_images["technical_helper"]
    expected = _expected_confidence(img.evidence_count)
    assert img.confidence == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# 13. Backward compatibility: DOMAIN_KEYWORDS alias still works
# ---------------------------------------------------------------------------

def test_domain_keywords_alias_is_same_as_default_seed_domains() -> None:
    """DOMAIN_KEYWORDS is a backward-compatible alias for DEFAULT_SEED_DOMAINS."""
    assert DOMAIN_KEYWORDS is DEFAULT_SEED_DOMAINS


def test_default_seed_domains_has_six_domains() -> None:
    """DEFAULT_SEED_DOMAINS contains the original 6 domain categories."""
    expected = {
        "technical_helper", "creative_writer", "knowledge_guide",
        "problem_solver", "creative_collaborator", "emotional_companion",
    }
    assert set(DEFAULT_SEED_DOMAINS.keys()) == expected


# ---------------------------------------------------------------------------
# 14. Emergent domain discovery: novel content creates new domains
# ---------------------------------------------------------------------------

def test_cooking_interaction_creates_cooking_domain(empty_manager: SelfModelManager) -> None:
    """A cooking interaction with no seed domains creates a cooking-related domain."""
    empty_manager.update_from_interaction(
        _interaction(
            "How do I make a sourdough bread recipe?",
            "Start with flour, water, and a sourdough starter",
        ),
        [],
    )
    images = empty_manager.self_images
    assert len(images) >= 1
    # The domain name should contain cooking-related keywords
    domain_names = list(images.keys())
    domain_joined = " ".join(domain_names)
    # At least one cooking-relevant word should appear in the domain name
    cooking_words = {"sourdough", "bread", "recipe", "flour", "starter", "water"}
    assert any(word in domain_joined for word in cooking_words), (
        f"Expected a cooking-related domain, got: {domain_names}"
    )


def test_fitness_interaction_creates_fitness_domain(empty_manager: SelfModelManager) -> None:
    """A fitness interaction with no seed domains creates a fitness-related domain."""
    empty_manager.update_from_interaction(
        _interaction(
            "What exercises should I do for a chest workout?",
            "Try bench press and pushups for chest strength",
        ),
        [],
    )
    images = empty_manager.self_images
    assert len(images) >= 1
    domain_names = list(images.keys())
    domain_joined = " ".join(domain_names)
    fitness_words = {"exercises", "chest", "workout", "bench", "pushups", "press", "strength"}
    assert any(word in domain_joined for word in fitness_words), (
        f"Expected a fitness-related domain, got: {domain_names}"
    )


def test_legal_interaction_creates_legal_domain(empty_manager: SelfModelManager) -> None:
    """A legal interaction with no seed domains creates a legal-related domain."""
    empty_manager.update_from_interaction(
        _interaction(
            "What are the requirements for filing a trademark?",
            "You need to file with the patent and trademark office",
        ),
        [],
    )
    images = empty_manager.self_images
    assert len(images) >= 1
    domain_names = list(images.keys())
    domain_joined = " ".join(domain_names)
    legal_words = {"trademark", "filing", "patent", "requirements", "office"}
    assert any(word in domain_joined for word in legal_words), (
        f"Expected a legal-related domain, got: {domain_names}"
    )


def test_novel_domain_does_not_match_seed_domains(manager: SelfModelManager) -> None:
    """Content completely outside seed domains creates a new emergent domain, not a seed domain."""
    manager.update_from_interaction(
        _interaction(
            "What fermentation temperature for kimchi?",
            "Keep the kimchi between 65-75 degrees fahrenheit for fermentation",
        ),
        [],
    )
    images = manager.self_images
    # Should NOT match any of the 6 seed domains
    seed_domain_names = set(DEFAULT_SEED_DOMAINS.keys())
    created_domains = set(images.keys())
    non_seed = created_domains - seed_domain_names
    assert len(non_seed) >= 1, (
        f"Expected a novel domain but only got seed domains: {created_domains}"
    )


# ---------------------------------------------------------------------------
# 15. Domain keywords grow over time
# ---------------------------------------------------------------------------

def test_domain_keywords_expand_with_interactions(manager: SelfModelManager) -> None:
    """When a domain is reinforced, new keywords from the interaction are added."""
    # First interaction: establishes technical_helper via "python" + "code"
    manager.update_from_interaction(
        _interaction("Review my python code", "Looks good"), []
    )
    initial_keywords = set(manager._domain_keywords["technical_helper"])

    # Second interaction: still matches technical_helper (python + code >= 2),
    # and introduces "refactor" + "module" as new vocabulary
    manager.update_from_interaction(
        _interaction("Refactor this python code module", "Here is the refactored version"), []
    )
    expanded_keywords = set(manager._domain_keywords["technical_helper"])

    assert expanded_keywords > initial_keywords, (
        "Domain keywords should grow as new content reinforces the domain"
    )
    assert "refactor" in expanded_keywords or "refactored" in expanded_keywords
    assert "module" in expanded_keywords


def test_emergent_domain_keywords_grow(empty_manager: SelfModelManager) -> None:
    """A newly created emergent domain expands its keywords on subsequent matches."""
    # First interaction: creates a cooking domain
    empty_manager.update_from_interaction(
        _interaction("How to bake sourdough bread?", "Mix flour and starter"), []
    )
    images = empty_manager.self_images
    domain_name = list(images.keys())[0]
    initial_keywords = set(empty_manager._domain_keywords[domain_name])

    # Second interaction: matching content expands the domain
    empty_manager.update_from_interaction(
        _interaction("What temperature for baking sourdough?", "Preheat oven to 450"), []
    )
    expanded_keywords = set(empty_manager._domain_keywords[domain_name])
    assert expanded_keywords >= initial_keywords, (
        "Domain keywords should not shrink"
    )


# ---------------------------------------------------------------------------
# 16. seed_domains constructor parameter
# ---------------------------------------------------------------------------

def test_custom_seed_domains() -> None:
    """Passing custom seed_domains replaces the defaults."""
    custom = {
        "music_theory": ["chord", "scale", "melody", "harmony", "rhythm"],
        "cooking": ["recipe", "ingredient", "bake", "cook", "simmer"],
    }
    manager = SelfModelManager(seed_domains=custom)

    # Music interaction should match the custom seed domain
    manager.update_from_interaction(
        _interaction("Explain the chord progression", "The harmony uses a I-IV-V"),
        [],
    )
    assert "music_theory" in manager.self_images

    # Technical interaction should NOT match (no seed for it)
    manager.update_from_interaction(
        _interaction("Debug python code", "Fixed"), []
    )
    # Should create a new emergent domain, not "technical_helper"
    assert "technical_helper" not in manager.self_images


def test_empty_seed_domains_starts_clean() -> None:
    """Passing an empty dict for seed_domains means all domains are emergent."""
    manager = SelfModelManager(seed_domains={})
    assert manager._domain_keywords == {}

    manager.update_from_interaction(
        _interaction("Tell me about quantum physics", "Quantum mechanics describes..."), []
    )
    images = manager.self_images
    assert len(images) >= 1
    # The domain should be emergent, not one of the defaults
    assert "technical_helper" not in images
    assert "knowledge_guide" not in images


def test_none_seed_domains_uses_defaults() -> None:
    """Passing None (or omitting) seed_domains loads DEFAULT_SEED_DOMAINS."""
    manager = SelfModelManager(seed_domains=None)
    assert set(manager._domain_keywords.keys()) == set(DEFAULT_SEED_DOMAINS.keys())


# ---------------------------------------------------------------------------
# 17. Serialization preserves domain_keywords
# ---------------------------------------------------------------------------

def test_to_dict_includes_domain_keywords(manager: SelfModelManager) -> None:
    """to_dict output includes the domain_keywords field."""
    data = manager.to_dict()
    assert "domain_keywords" in data
    # Default seeds should be present
    assert "technical_helper" in data["domain_keywords"]


def test_round_trip_preserves_domain_keywords(manager: SelfModelManager) -> None:
    """Serializing and deserializing preserves learned domain keywords."""
    manager.update_from_interaction(
        _interaction("Review my python code for bugs", "Found two issues"), []
    )
    original_data = manager.to_dict()
    original_keywords = {
        d: set(kws) for d, kws in original_data["domain_keywords"].items()
    }

    restored = SelfModelManager.from_dict(original_data)
    restored_keywords = {
        d: set(kws) for d, kws in restored.to_dict()["domain_keywords"].items()
    }

    assert restored_keywords == original_keywords


def test_round_trip_preserves_emergent_domains(empty_manager: SelfModelManager) -> None:
    """Emergent domains survive serialization round-trip."""
    empty_manager.update_from_interaction(
        _interaction("Teach me guitar chords", "Start with open chords"), []
    )
    domain_name = list(empty_manager.self_images.keys())[0]

    restored = SelfModelManager.from_dict(empty_manager.to_dict())
    assert domain_name in restored.self_images
    assert domain_name in restored._domain_keywords


# ---------------------------------------------------------------------------
# 18. Stop words are filtered
# ---------------------------------------------------------------------------

def test_stop_words_do_not_create_domains(empty_manager: SelfModelManager) -> None:
    """An interaction made entirely of stop words should not create any domain."""
    # All these words are either < 3 chars or in STOP_WORDS
    empty_manager.update_from_interaction(
        _interaction("Can you help me with this?", "Sure, let me help you"), []
    )
    assert empty_manager.self_images == {}


def test_stop_words_are_not_empty() -> None:
    """STOP_WORDS should contain a reasonable number of common English words."""
    assert len(STOP_WORDS) >= 50


def test_common_conversational_words_are_stop_words() -> None:
    """Words like 'help', 'please', 'thanks' should be in the stop word list."""
    for word in ["help", "please", "thanks", "sure", "hello"]:
        assert word in STOP_WORDS, f"Expected '{word}' to be a stop word"


def test_meaningful_words_survive_stop_word_filter() -> None:
    """Domain-specific words like 'python', 'recipe', 'exercise' should NOT be stop words."""
    for word in ["python", "recipe", "exercise", "algorithm", "melody"]:
        assert word not in STOP_WORDS, f"'{word}' should NOT be a stop word"
