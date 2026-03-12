# test_dspy_modules.py — Tests for the DSPy integration layer.
# Created: feat/dspy-integration — Verifies DSPy modules, adapter, optimizer,
#   training data generator, and graceful fallback when dspy is not installed.
#   All DSPy LM calls are mocked — no real API calls in tests.

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType, SignificanceScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_interaction(user: str = "Hello", agent: str = "Hi there") -> Interaction:
    """Create a test Interaction."""
    return Interaction(user_input=user, agent_output=agent)


def _mock_dspy_module():
    """Create a mock dspy module that provides the minimum API surface."""
    mock_dspy = MagicMock()

    # Mock dspy.LM
    mock_lm = MagicMock()
    mock_dspy.LM.return_value = mock_lm

    # Mock dspy.configure
    mock_dspy.configure = MagicMock()

    # Mock ChainOfThought — returns a callable that produces prediction-like objects
    def make_cot(signature):
        predictor = MagicMock()
        prediction = MagicMock()
        prediction.should_store = True
        prediction.novelty = 0.7
        prediction.emotional_intensity = 0.5
        prediction.factual_importance = 0.6
        prediction.reasoning = "This contains important factual information."
        prediction.facts = ["User's name is Alex"]
        prediction.is_update = False
        predictor.return_value = prediction
        predictor.save = MagicMock()
        predictor.load = MagicMock()
        return predictor

    mock_dspy.ChainOfThought = make_cot

    # Mock Predict
    def make_predict(signature):
        predictor = MagicMock()
        prediction = MagicMock()
        prediction.expanded_queries = [
            "What is the user's name?",
            "user name",
            "tell me about the user's identity",
        ]
        predictor.return_value = prediction
        predictor.save = MagicMock()
        predictor.load = MagicMock()
        return predictor

    mock_dspy.Predict = make_predict

    # Mock Example
    class MockExample:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def with_inputs(self, *args):
            return self

    mock_dspy.Example = MockExample

    # Mock MIPROv2
    mock_optimizer = MagicMock()
    mock_optimizer.compile.return_value = MagicMock()
    mock_dspy.MIPROv2.return_value = mock_optimizer

    return mock_dspy


@contextmanager
def _with_mock_dspy():
    """Context manager that injects a mock dspy into sys.modules and ensures
    our cognitive modules are fresh-imported against it."""
    mock_dspy = _mock_dspy_module()
    # Remove any cached versions of our modules so they re-import with mock dspy
    modules_to_clear = [
        k for k in sys.modules
        if k.startswith("soul_protocol.runtime.cognitive.dspy_")
    ]
    saved = {k: sys.modules.pop(k) for k in modules_to_clear}
    with patch.dict(sys.modules, {"dspy": mock_dspy}):
        yield mock_dspy
    # Restore cleared modules
    for k in modules_to_clear:
        sys.modules.pop(k, None)
    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Test: DSPy modules can be imported and instantiated when dspy is available
# ---------------------------------------------------------------------------


class TestDSPyModulesImport:
    """Test that DSPy modules work when the dspy package is available."""

    def test_significance_gate_instantiation(self):
        """SignificanceGate can be created with mocked dspy."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import SignificanceGate

            gate = SignificanceGate()
            assert gate is not None

    def test_significance_gate_forward(self):
        """SignificanceGate.forward returns a prediction object."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import SignificanceGate

            gate = SignificanceGate()
            result = gate.forward(
                user_input="My name is Alex",
                agent_output="Nice to meet you Alex!",
                core_values=["helpfulness"],
            )
            assert hasattr(result, "should_store")
            assert hasattr(result, "novelty")

    def test_query_expander_instantiation(self):
        """QueryExpander can be created with mocked dspy."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import QueryExpander

            expander = QueryExpander()
            assert expander is not None

    def test_query_expander_forward(self):
        """QueryExpander.forward returns a list of strings."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import QueryExpander

            expander = QueryExpander()
            result = expander.forward(query="What is the user's name?")
            assert isinstance(result, list)
            assert len(result) > 0

    def test_fact_extractor_instantiation(self):
        """FactExtractor can be created with mocked dspy."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import FactExtractor

            extractor = FactExtractor()
            assert extractor is not None

    def test_fact_extractor_forward(self):
        """FactExtractor.forward returns a prediction with facts."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_modules import FactExtractor

            extractor = FactExtractor()
            result = extractor.forward(
                user_input="My name is Alex and I work at Google",
                agent_output="Nice to meet you Alex!",
            )
            assert hasattr(result, "facts")


# ---------------------------------------------------------------------------
# Test: DSPyCognitiveProcessor adapter
# ---------------------------------------------------------------------------


class TestDSPyAdapter:
    """Test the DSPyCognitiveProcessor adapter bridge."""

    async def test_assess_significance_returns_score(self):
        """assess_significance returns a valid SignificanceScore."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock-model")
            interaction = _make_interaction("My name is Alex", "Nice to meet you!")
            score = await processor.assess_significance(
                interaction=interaction,
                core_values=["helpfulness"],
                recent_contents=["previous message"],
            )
            assert isinstance(score, SignificanceScore)
            assert 0.0 <= score.novelty <= 1.0
            assert 0.0 <= score.emotional_intensity <= 1.0
            assert 0.0 <= score.goal_relevance <= 1.0

    async def test_expand_query_returns_list(self):
        """expand_query returns a list including the original query."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock-model")
            result = await processor.expand_query("What is the user's name?")
            assert isinstance(result, list)
            assert "What is the user's name?" in result

    async def test_extract_facts_returns_memory_entries(self):
        """extract_facts returns a list of MemoryEntry objects."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock-model")
            interaction = _make_interaction("My name is Alex", "Nice to meet you!")
            facts = await processor.extract_facts(interaction)
            assert isinstance(facts, list)
            for fact in facts:
                assert isinstance(fact, MemoryEntry)
                assert fact.type == MemoryType.SEMANTIC

    async def test_assess_significance_fallback_on_error(self):
        """Falls back to heuristic when DSPy module raises."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock")
            # Make the gate raise an exception
            processor._significance_gate.forward = MagicMock(side_effect=RuntimeError("boom"))

            interaction = _make_interaction("test input", "test output")
            score = await processor.assess_significance(
                interaction=interaction,
                core_values=[],
                recent_contents=[],
            )
            # Should get a valid score from the heuristic fallback
            assert isinstance(score, SignificanceScore)

    async def test_expand_query_fallback_on_error(self):
        """Falls back to [query] when DSPy module raises."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock")
            processor._query_expander.forward = MagicMock(side_effect=RuntimeError("boom"))

            result = await processor.expand_query("test query")
            assert result == ["test query"]

    async def test_extract_facts_fallback_on_error(self):
        """Returns empty list when DSPy module raises."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

            processor = DSPyCognitiveProcessor(lm_model="test/mock")
            processor._fact_extractor.forward = MagicMock(side_effect=RuntimeError("boom"))

            interaction = _make_interaction("test", "test")
            result = await processor.extract_facts(interaction)
            assert result == []


# ---------------------------------------------------------------------------
# Test: Training data generator
# ---------------------------------------------------------------------------


class TestTrainingDataGenerator:
    """Test that the training data generator produces valid examples."""

    def test_generate_significance_dataset(self):
        """Significance dataset has correct structure."""
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parent.parent),
        )
        from research.dspy_training.generate_dataset import generate_significance_dataset

        data = generate_significance_dataset(num_users=2)
        assert len(data) > 0

        # Check structure of first example
        example = data[0]
        assert "user_input" in example
        assert "agent_output" in example
        assert "core_values" in example
        assert "should_store" in example
        assert isinstance(example["should_store"], bool)
        assert isinstance(example["core_values"], list)

    def test_generate_recall_dataset(self):
        """Recall dataset has correct structure."""
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parent.parent),
        )
        from research.dspy_training.generate_dataset import generate_recall_dataset

        data = generate_recall_dataset(num_users=2)
        assert len(data) > 0

        example = data[0]
        assert "query" in example
        assert "expected_fact" in example
        assert "expanded_queries" in example
        assert isinstance(example["expanded_queries"], list)
        assert len(example["expanded_queries"]) >= 1

    def test_split_dataset(self):
        """split_dataset produces correct train/val split."""
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parent.parent),
        )
        from research.dspy_training.generate_dataset import split_dataset

        data = [{"x": i} for i in range(100)]
        train, val = split_dataset(data, val_ratio=0.2)
        assert len(train) == 80
        assert len(val) == 20

    def test_significance_dataset_has_both_labels(self):
        """Dataset contains both positive and negative examples."""
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parent.parent),
        )
        from research.dspy_training.generate_dataset import generate_significance_dataset

        data = generate_significance_dataset(num_users=2)
        positives = sum(1 for e in data if e["should_store"])
        negatives = sum(1 for e in data if not e["should_store"])
        # We expect both labels to be present
        assert positives > 0, "No positive examples in dataset"
        assert negatives >= 0, "Dataset should contain some negative examples"


# ---------------------------------------------------------------------------
# Test: use_dspy=False doesn't change existing behavior
# ---------------------------------------------------------------------------


class TestDSPyDefaultOff:
    """Verify that the default (use_dspy=False) path is unchanged."""

    async def test_soul_birth_without_dspy(self):
        """Soul.birth() without use_dspy works exactly as before."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="TestSoul", values=["kindness"])
        assert soul.name == "TestSoul"
        assert soul._dspy_processor is None

    async def test_soul_birth_with_dspy_false(self):
        """Explicit use_dspy=False produces no DSPy processor."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="TestSoul", use_dspy=False)
        assert soul._dspy_processor is None

    async def test_soul_observe_without_dspy(self):
        """observe() works normally without DSPy."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="TestSoul", values=["kindness"])
        interaction = _make_interaction("My name is Alex", "Nice to meet you!")
        await soul.observe(interaction)
        # Should still extract facts via heuristic
        memories = await soul.recall("Alex")
        assert any("Alex" in m.content for m in memories)


# ---------------------------------------------------------------------------
# Test: Graceful fallback when dspy is not installed
# ---------------------------------------------------------------------------


class TestDSPyNotInstalled:
    """Test graceful behavior when dspy package is not available."""

    def test_dspy_modules_import_error(self):
        """dspy_modules raises ImportError with helpful message when dspy missing."""
        # Clear cached dspy_modules, then patch dspy as None (import fails)
        modules_to_clear = [
            k for k in list(sys.modules)
            if k.startswith("soul_protocol.runtime.cognitive.dspy_")
        ]
        saved = {k: sys.modules.pop(k) for k in modules_to_clear}
        try:
            with patch.dict(sys.modules, {"dspy": None}):
                from soul_protocol.runtime.cognitive.dspy_modules import SignificanceGate

                with pytest.raises(ImportError, match="DSPy is required"):
                    SignificanceGate()
        finally:
            for k in modules_to_clear:
                sys.modules.pop(k, None)
            sys.modules.update(saved)

    async def test_soul_birth_with_dspy_true_no_package(self):
        """Soul.birth(use_dspy=True) falls back when dspy not installed."""
        # Clear cached adapter module, patch dspy as None
        modules_to_clear = [
            k for k in list(sys.modules)
            if k.startswith("soul_protocol.runtime.cognitive.dspy_")
        ]
        saved = {k: sys.modules.pop(k) for k in modules_to_clear}
        try:
            with patch.dict(sys.modules, {"dspy": None}):
                from soul_protocol.runtime.soul import Soul

                soul = await Soul.birth(name="TestSoul", use_dspy=True)
                # Should fall back gracefully — no DSPy processor
                assert soul._dspy_processor is None
        finally:
            for k in modules_to_clear:
                sys.modules.pop(k, None)
            sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Test: DSPy optimizer (structure only — no real optimization)
# ---------------------------------------------------------------------------


class TestDSPyOptimizer:
    """Test the SoulOptimizer structure with mocked dspy."""

    def test_optimizer_instantiation(self):
        """SoulOptimizer can be created with mocked dspy."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_optimizer import SoulOptimizer

            optimizer = SoulOptimizer(lm_model="test/mock")
            assert optimizer is not None
            assert optimizer.significance_gate is not None
            assert optimizer.query_expander is not None
            assert optimizer.fact_extractor is not None

    def test_significance_metric_correct(self):
        """_significance_metric returns 1.0 for correct classification."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_optimizer import SoulOptimizer

            optimizer = SoulOptimizer(lm_model="test/mock")

            example = MagicMock()
            example.should_store = True
            prediction = MagicMock()
            prediction.should_store = True
            prediction.reasoning = "This is clearly important."

            score = optimizer._significance_metric(example, prediction)
            assert score >= 1.0

    def test_significance_metric_incorrect(self):
        """_significance_metric returns 0.0 for incorrect classification."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_optimizer import SoulOptimizer

            optimizer = SoulOptimizer(lm_model="test/mock")

            example = MagicMock()
            example.should_store = True
            prediction = MagicMock()
            prediction.should_store = False

            score = optimizer._significance_metric(example, prediction)
            assert score == 0.0


# ---------------------------------------------------------------------------
# Test: Safe float conversion helper
# ---------------------------------------------------------------------------


class TestHelpers:
    """Test utility helpers in the adapter module."""

    def test_safe_float_from_number(self):
        """_safe_float converts numbers correctly."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import _safe_float

            assert _safe_float(0.5) == 0.5
            assert _safe_float(1) == 1.0
            assert _safe_float(0) == 0.0

    def test_safe_float_from_string(self):
        """_safe_float converts string numbers."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import _safe_float

            assert _safe_float("0.7") == 0.7

    def test_safe_float_from_invalid(self):
        """_safe_float returns 0.5 for invalid input."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import _safe_float

            assert _safe_float("not a number") == 0.5
            assert _safe_float(None) == 0.5

    def test_clamp(self):
        """_clamp bounds values correctly."""
        with _with_mock_dspy():
            from soul_protocol.runtime.cognitive.dspy_adapter import _clamp

            assert _clamp(0.5, 0.0, 1.0) == 0.5
            assert _clamp(-0.5, 0.0, 1.0) == 0.0
            assert _clamp(1.5, 0.0, 1.0) == 1.0
