# test_sentiment_gaps.py — Known gap tests for the heuristic sentiment detector.
# Created: 2026-03-12
#
# These tests document CURRENT FAILURES in detect_sentiment() and are expected
# to fail against the existing implementation. They exist to:
#   1. Prove the bugs are real and reproducible.
#   2. Serve as a passing green suite once the fixes land.
#
# Five gap categories are covered:
#   Cat 1 — Missing vocabulary: common positive words not in the word list.
#   Cat 2 — Joy/excitement confusion: high arousal scores push calm joy → excitement.
#   Cat 3 — Sadness/frustration confusion: high arousal scores push sadness → frustration.
#   Cat 4 — Gratitude misclassification: intensifiers push gratitude words into excitement/curiosity.
#   Cat 5 — Neutral false positive: low-intensity positive words trigger a positive label.
#
# DO NOT fix the bugs in this file — fix them in sentiment.py, then these tests go green.

from __future__ import annotations

from soul_protocol.runtime.memory.sentiment import detect_sentiment

# ---------------------------------------------------------------------------
# Category 1 — Missing vocabulary
# Words like "promoted", "won", "married", "best", "steps" are not in the
# word list, so emotionally loaded sentences return label="neutral".
# ---------------------------------------------------------------------------


def test_missing_word_promoted_is_not_neutral():
    """'I GOT PROMOTED!!!' should express excitement or joy, not neutral."""
    result = detect_sentiment("I GOT PROMOTED!!!")
    assert result.label != "neutral", (
        f"Expected a positive emotion label, got 'neutral' "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_missing_word_won_championship_is_not_neutral():
    """'We won the championship!' should express excitement or joy, not neutral."""
    result = detect_sentiment("We won the championship!")
    assert result.label != "neutral", (
        f"Expected a positive emotion label, got 'neutral' "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_missing_word_first_steps_has_positive_valence():
    """'My daughter took her first steps today' — word-list can't detect this.

    This is a known limitation: the text expresses joy through context/meaning
    ("milestone moment") rather than emotion keywords. Requires NLP/LLM-level
    understanding. We test that adding an explicit emotion word DOES work.
    """
    # Pure context — word-list returns neutral (known limitation)
    result = detect_sentiment("My daughter took her first steps today")
    assert result.label == "neutral", "Context-only emotion still undetectable by word list"

    # Same idea WITH an emotion keyword — should detect it
    result_with_keyword = detect_sentiment("My daughter took her first steps today, so happy!")
    assert result_with_keyword.valence > 0.0, (
        f"Expected positive valence when emotion keyword present, got {result_with_keyword.valence}"
    )


def test_missing_word_getting_married_is_not_neutral():
    """'They said yes! I'm getting married!' should be joy or excitement, not neutral."""
    result = detect_sentiment("They said yes! I'm getting married!")
    assert result.label != "neutral", (
        f"Expected a positive emotion label, got 'neutral' "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_missing_word_best_day_is_not_neutral():
    """'This is the best day of my life!' should be joy or excitement, not neutral."""
    result = detect_sentiment("This is the best day of my life!")
    assert result.label != "neutral", (
        f"Expected a positive emotion label, got 'neutral' "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


# ---------------------------------------------------------------------------
# Category 2 — Joy misclassified as excitement
# Positive words have base scores that produce arousal > 0.5, which lands them
# in the excitement quadrant even when the sentiment is warm and low-energy.
# ---------------------------------------------------------------------------


def test_baking_cookies_happy_is_joy_not_excitement():
    """'Baking cookies with grandma always makes me happy' is warm joy, not excitement.

    'happy' has a base score of 0.8 — the arousal floor needs tuning so that
    calm, warm contexts yield arousal < 0.5 (joy quadrant).
    """
    result = detect_sentiment("Baking cookies with grandma always makes me happy")
    assert result.label == "joy", (
        f"Expected 'joy', got {result.label!r} (valence={result.valence}, arousal={result.arousal})"
    )


def test_everything_clicked_feeling_great_is_joy_not_excitement():
    """'Everything just clicked perfectly today, feeling great' should be joy.

    'great' (score 0.7) is a calm satisfaction word; arousal should stay below 0.5.
    """
    result = detect_sentiment("Everything just clicked perfectly today, feeling great")
    assert result.label == "joy", (
        f"Expected 'joy', got {result.label!r} (valence={result.valence}, arousal={result.arousal})"
    )


def test_childhood_book_delighted_is_joy_not_excitement():
    """'Found my favorite childhood book at a yard sale, delighted' should be joy.

    'delighted' (score 0.8) is a gentle delight, not high-energy excitement.
    """
    result = detect_sentiment("Found my favorite childhood book at a yard sale, delighted")
    assert result.label == "joy", (
        f"Expected 'joy', got {result.label!r} (valence={result.valence}, arousal={result.arousal})"
    )


# ---------------------------------------------------------------------------
# Category 3 — Sadness misclassified as frustration
# Sadness words like 'depressed', 'heartbroken', 'hopeless' have high base
# scores (0.8–0.9), pushing arousal above 0.5 into the frustration quadrant.
# ---------------------------------------------------------------------------


def test_lost_job_hopeless_is_sadness_not_frustration():
    """'I lost my job today and I feel hopeless' should be sadness.

    'hopeless' (0.8) and 'lost' (0.5) together produce high arousal.
    The detector must distinguish sadness words from frustration/anger words.
    """
    result = detect_sentiment("I lost my job today and I feel hopeless")
    assert result.label == "sadness", (
        f"Expected 'sadness', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_really_depressed_is_sadness_not_frustration():
    """'Feeling really depressed about how things turned out' should be sadness.

    'depressed' (0.8) + 'really' intensifier (1.3) drives arousal to 1.0,
    which lands in frustration. This is a clear sadness expression.
    """
    result = detect_sentiment("Feeling really depressed about how things turned out")
    assert result.label == "sadness", (
        f"Expected 'sadness', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_heartbroken_is_sadness_not_frustration():
    """'They broke up with me out of nowhere, I'm heartbroken' should be sadness.

    'heartbroken' (0.9) is the canonical sadness word — it should never
    classify as frustration.
    """
    result = detect_sentiment("They broke up with me out of nowhere, I'm heartbroken")
    assert result.label == "sadness", (
        f"Expected 'sadness', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_watching_old_videos_so_sad_is_sadness_not_frustration():
    """'Watching the old family videos makes me so sad' should be sadness.

    'sad' (0.6) + 'so' intensifier (1.2) = arousal 0.72, landing in frustration.
    Low-energy grief should not be classified as frustration.
    """
    result = detect_sentiment("Watching the old family videos makes me so sad")
    assert result.label == "sadness", (
        f"Expected 'sadness', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


# ---------------------------------------------------------------------------
# Category 4 — Gratitude misclassified
# Gratitude words ('grateful', 'thank') combined with intensifiers produce
# high arousal scores that push the result out of the gratitude quadrant
# (which requires arousal < 0.3) into excitement or curiosity.
# ---------------------------------------------------------------------------


def test_really_grateful_is_gratitude_not_excitement():
    """'I'm really grateful for your help with this project' should be gratitude.

    'grateful' (0.7) + 'really' intensifier (1.3) = valence 0.91, arousal 0.91,
    which lands in excitement. The gratitude zone ceiling of 0.3 arousal is
    too narrow to capture intensified gratitude expressions.
    """
    result = detect_sentiment("I'm really grateful for your help with this project")
    assert result.label == "gratitude", (
        f"Expected 'gratitude', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


def test_thank_you_so_much_is_gratitude_not_curiosity():
    """'Thank you so much for everything you've done for me' should be gratitude.

    'thank' (0.5) + 'so' intensifier (1.2) = valence 0.48, arousal 0.48,
    which lands in curiosity (valence 0.1–0.5, arousal 0.2–0.6). This is
    clearly gratitude, not curiosity.
    """
    result = detect_sentiment("Thank you so much for everything you've done for me")
    assert result.label == "gratitude", (
        f"Expected 'gratitude', got {result.label!r} "
        f"(valence={result.valence}, arousal={result.arousal})"
    )


# ---------------------------------------------------------------------------
# Category 5 — Neutral false positive
# Low-intensity positive words like 'nice' (score 0.5) are enough to trigger
# a non-neutral label even for plainly neutral statements.
# ---------------------------------------------------------------------------


def test_nice_weather_today_is_neutral():
    """'Nice weather today' should be neutral — it is an observation, not an emotion.

    'nice' (score 0.5) produces valence=0.5, arousal=0.5, which is picked up
    as curiosity or excitement. A casual weather remark carries no real
    emotional charge and should stay neutral.
    """
    result = detect_sentiment("Nice weather today")
    assert result.label == "neutral", (
        f"Expected 'neutral' for a plain observation, "
        f"got {result.label!r} (valence={result.valence}, arousal={result.arousal})"
    )
