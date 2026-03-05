# test_sentiment.py — Tests for heuristic sentiment detection (Damasio somatic markers).
# Created: 2026-02-22 — ~20 cases covering neutral, positive, negative, mixed,
#   intensifiers, negation, empty input, edge text, and label accuracy.

from __future__ import annotations

from soul_protocol.memory.sentiment import detect_sentiment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _within(value: float, expected: float, tolerance: float = 0.05) -> bool:
    """True if value is within tolerance of expected."""
    return abs(value - expected) <= tolerance


# ---------------------------------------------------------------------------
# 1. Neutral text — no emotion words
# ---------------------------------------------------------------------------


def test_neutral_text_returns_neutral_label():
    """Text with no emotion words produces the 'neutral' label."""
    result = detect_sentiment("The sky is blue and the water is clear.")
    assert result.label == "neutral"


def test_neutral_text_valence_near_zero():
    """Text with no emotion words produces near-zero valence."""
    result = detect_sentiment("The sky is blue and the water is clear.")
    assert abs(result.valence) < 0.05


def test_neutral_text_arousal_near_zero():
    """Text with no emotion words produces near-zero arousal."""
    result = detect_sentiment("The sky is blue and the water is clear.")
    assert abs(result.arousal) < 0.05


# ---------------------------------------------------------------------------
# 2. Empty string
# ---------------------------------------------------------------------------


def test_empty_string_returns_neutral():
    """Empty string immediately returns the neutral SomaticMarker."""
    result = detect_sentiment("")
    assert result.label == "neutral"
    assert result.valence == 0.0
    assert result.arousal == 0.0


# ---------------------------------------------------------------------------
# 3. Only stop words / short text with no emotion content
# ---------------------------------------------------------------------------


def test_only_stop_words_returns_neutral():
    """Text made entirely of articles and prepositions produces neutral."""
    result = detect_sentiment("the a an in on at of")
    assert result.label == "neutral"
    assert result.valence == 0.0
    assert result.arousal == 0.0


def test_single_neutral_word_returns_neutral():
    """A single word not in any emotion list produces neutral."""
    result = detect_sentiment("Tuesday")
    assert result.label == "neutral"


# ---------------------------------------------------------------------------
# 4. Positive text
# ---------------------------------------------------------------------------


def test_positive_word_yields_positive_valence():
    """A clearly positive word ('amazing') yields positive valence."""
    result = detect_sentiment("This is amazing!")
    assert result.valence > 0.0


def test_positive_word_yields_positive_arousal():
    """A clearly positive word yields non-zero arousal."""
    result = detect_sentiment("This is amazing!")
    assert result.arousal > 0.0


def test_strong_positive_word_yields_high_valence():
    """A high-score positive word like 'love' yields valence close to its score."""
    result = detect_sentiment("I love this")
    # 'love' scores 0.9 — expect valence around that value
    assert result.valence >= 0.7


def test_single_positive_word_excitement_label():
    """'excited' alone maps to the 'excitement' label (high valence + high arousal)."""
    result = detect_sentiment("I am so excited!")
    # 'excited' = 0.8; 'so' intensifier = 1.2 → arousal >= 0.5 → excitement region
    assert result.label == "excitement"
    assert result.valence > 0.0


# ---------------------------------------------------------------------------
# 5. Negative text
# ---------------------------------------------------------------------------


def test_negative_word_yields_negative_valence():
    """A clearly negative word ('terrible') yields negative valence."""
    result = detect_sentiment("This is terrible")
    assert result.valence < 0.0


def test_strong_negative_word_frustration_label():
    """'frustrated' alone maps to the 'frustration' label."""
    result = detect_sentiment("I am so frustrated")
    assert result.label == "frustration"


def test_high_intensity_negative_yields_frustration():
    """'terrible' (score 0.8) produces high arousal → frustration, not sadness."""
    result = detect_sentiment("That was terrible")
    assert result.label == "frustration"
    assert result.valence < -0.3
    assert result.arousal >= 0.5


# ---------------------------------------------------------------------------
# 6. Mixed positive and negative
# ---------------------------------------------------------------------------


def test_mixed_emotion_net_valence_direction():
    """'happy but frustrated' — net valence depends on which word dominates."""
    result = detect_sentiment("I am happy but frustrated with this")
    # happy=0.8, frustrated=0.7 → net=(0.8-0.7)=0.1 → very mild positive
    assert isinstance(result.valence, float)  # basic sanity
    # Net should be close to zero (within ±0.2) when scores nearly balance
    assert abs(result.valence) < 0.2


def test_strong_positive_dominates_weak_negative():
    """When positive score is much higher, net valence is positive."""
    result = detect_sentiment("This is absolutely wonderful, only a tiny issue")
    # wonderful=0.9 * intensifier=1.4; issue=0.3 → positive dominates
    assert result.valence > 0.0


def test_strong_negative_dominates_weak_positive():
    """When negative score is much higher, net valence is negative."""
    result = detect_sentiment("This is awful, just okay at best")
    # awful=0.8; okay=0.2 → negative dominates
    assert result.valence < 0.0


# ---------------------------------------------------------------------------
# 7. Intensifiers
# ---------------------------------------------------------------------------


def test_intensifier_raises_score_above_baseline():
    """'very happy' produces higher valence than 'happy' alone."""
    baseline = detect_sentiment("happy")
    intensified = detect_sentiment("very happy")
    # Intensifier multiplies raw valence — capped at 1.0 but intensified >= baseline
    assert intensified.valence >= baseline.valence


def test_extremely_boosts_arousal_above_baseline():
    """'extremely frustrated' has higher arousal than 'frustrated' alone."""
    baseline = detect_sentiment("frustrated")
    intensified = detect_sentiment("extremely frustrated")
    assert intensified.arousal >= baseline.arousal


def test_intensifier_does_not_flip_sign():
    """An intensifier applied to a positive word keeps valence positive."""
    result = detect_sentiment("really happy")
    assert result.valence > 0.0


# ---------------------------------------------------------------------------
# 8. Negation
# ---------------------------------------------------------------------------


def test_negation_flips_positive_to_negative_valence():
    """'not happy' flips the positive score into a negative valence."""
    result = detect_sentiment("not happy")
    assert result.valence < 0.0


def test_negation_of_negative_yields_mild_positive_valence():
    """'not bad' flips a negative word into a mild positive valence."""
    result = detect_sentiment("not bad")
    assert result.valence > 0.0


def test_dont_negation_works():
    """'don't' (contracted negation) also triggers valence flip."""
    detect_sentiment("I don't like this at all")
    # 'like' is not in word lists, but this tests the contraction is parsed
    # Use 'happy' to ensure the negation effect is observable
    negated = detect_sentiment("I don't feel happy about this")
    assert negated.valence < 0.0


def test_negation_window_three_words():
    """Negation applies within a 3-word window before the emotion word."""
    # 'not' is 2 positions before 'good' → should negate
    result = detect_sentiment("it is not good")
    assert result.valence < 0.0

    # 'not' is 4 positions before 'good' → outside window, should NOT negate
    result_outside = detect_sentiment("not and then again good")
    assert result_outside.valence > 0.0


# ---------------------------------------------------------------------------
# 9. Label accuracy — specific emotion labels
# ---------------------------------------------------------------------------


def test_curiosity_label_for_curious_word():
    """'curious' alone maps to the 'curiosity' label (mid valence, mid-low arousal)."""
    result = detect_sentiment("curious")
    assert result.label == "curiosity"


def test_confusion_label_for_confused_word():
    """'confused' alone maps to the 'confusion' label (mild negative, mid arousal)."""
    result = detect_sentiment("confused")
    assert result.label == "confusion"


def test_frustration_label_for_angry_word():
    """'furious' maps to 'frustration' (strong negative, high arousal)."""
    result = detect_sentiment("furious")
    assert result.label == "frustration"


def test_excitement_label_for_thrilled():
    """'thrilled' maps to 'excitement' (strong positive, high arousal)."""
    result = detect_sentiment("thrilled")
    assert result.label == "excitement"


# ---------------------------------------------------------------------------
# 10. SomaticMarker shape and bounds
# ---------------------------------------------------------------------------


def test_result_is_somatic_marker_with_required_fields():
    """detect_sentiment always returns an object with valence, arousal, and label."""
    result = detect_sentiment("something random")
    assert hasattr(result, "valence")
    assert hasattr(result, "arousal")
    assert hasattr(result, "label")


def test_valence_always_in_range():
    """valence is always clamped to [-1.0, 1.0]."""
    for text in [
        "absolutely incredibly extremely totally amazing wonderful fantastic",
        "absolutely incredibly extremely totally terrible awful horrible",
        "",
        "meh",
    ]:
        result = detect_sentiment(text)
        assert -1.0 <= result.valence <= 1.0, f"valence={result.valence} out of range for: {text!r}"


def test_arousal_always_in_range():
    """arousal is always clamped to [0.0, 1.0]."""
    for text in [
        "absolutely incredibly extremely totally amazing wonderful fantastic",
        "absolutely incredibly extremely totally terrible awful horrible",
        "",
        "meh",
    ]:
        result = detect_sentiment(text)
        assert 0.0 <= result.arousal <= 1.0, f"arousal={result.arousal} out of range for: {text!r}"
