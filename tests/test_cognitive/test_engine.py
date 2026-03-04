# tests/test_cognitive/test_engine.py — Tests for CognitiveEngine, HeuristicEngine,
#   CognitiveProcessor, and integration with Soul/MemoryManager.
# Created: v0.2.1
# Updated: 2026-03-04 — Regression tests for _is_heuristic_only bug: passing
#   engine=HeuristicEngine() explicitly must preserve heuristic self-model path.

from __future__ import annotations

import json

import pytest

from soul_protocol import Soul
from soul_protocol.cognitive.engine import (
    CognitiveEngine,
    CognitiveProcessor,
    HeuristicEngine,
    _clamp,
    _extract_field,
    _extract_task_marker,
    _parse_json,
)
from soul_protocol.types import (
    Interaction,
    MemoryEntry,
    MemoryType,
    ReflectionResult,
    SelfImage,
    SignificanceScore,
    SomaticMarker,
)


# ---------------------------------------------------------------------------
# Mock LLM engine for testing
# ---------------------------------------------------------------------------


class MockLLMEngine:
    """Mock engine returning predefined JSON responses keyed by task marker."""

    def __init__(self, responses: dict[str, dict | list] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    async def think(self, prompt: str) -> str:
        self.calls.append(prompt)
        task = _extract_task_marker(prompt)
        if task in self.responses:
            return json.dumps(self.responses[task])
        return json.dumps({})


class FailingEngine:
    """Engine that always raises."""

    async def think(self, prompt: str) -> str:
        raise RuntimeError("LLM unavailable")


class GarbageEngine:
    """Engine that returns non-JSON garbage."""

    async def think(self, prompt: str) -> str:
        return "This is not JSON at all ¯\\_(ツ)_/¯"


# ---------------------------------------------------------------------------
# CognitiveEngine protocol compliance
# ---------------------------------------------------------------------------


class TestCognitiveEngineProtocol:
    def test_mock_engine_satisfies_protocol(self) -> None:
        engine = MockLLMEngine()
        assert isinstance(engine, CognitiveEngine)

    def test_heuristic_engine_satisfies_protocol(self) -> None:
        engine = HeuristicEngine()
        assert isinstance(engine, CognitiveEngine)


# ---------------------------------------------------------------------------
# HeuristicEngine.think() routing
# ---------------------------------------------------------------------------


class TestHeuristicEngine:
    @pytest.mark.asyncio
    async def test_sentiment_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think("[TASK:sentiment]\nText: I am very happy today")
        data = json.loads(result)
        assert "valence" in data
        assert "arousal" in data
        assert "label" in data
        assert data["valence"] > 0  # "happy" → positive

    @pytest.mark.asyncio
    async def test_significance_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think(
            "[TASK:significance]\nUser: I love this project\nAgent: Glad to help"
        )
        data = json.loads(result)
        assert "novelty" in data
        assert "emotional_intensity" in data
        assert "goal_relevance" in data

    @pytest.mark.asyncio
    async def test_extract_facts_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think(
            "[TASK:extract_facts]\nUser: My name is Alice\nAgent: Nice to meet you"
        )
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "Alice" in data[0]["content"]

    @pytest.mark.asyncio
    async def test_extract_entities_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think(
            "[TASK:extract_entities]\nUser: I use Python\nAgent: Great choice"
        )
        data = json.loads(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_self_reflection_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think("[TASK:self_reflection]\nRecent: coding")
        data = json.loads(result)
        assert "self_images" in data
        assert "insights" in data

    @pytest.mark.asyncio
    async def test_reflect_routing(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think("[TASK:reflect]\nEpisodes: ...")
        data = json.loads(result)
        assert "themes" in data
        assert "summaries" in data

    @pytest.mark.asyncio
    async def test_unknown_task_returns_error(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think("[TASK:nonexistent]\nData: something")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_no_task_marker_returns_error(self) -> None:
        engine = HeuristicEngine()
        result = await engine.think("Just a random prompt with no marker")
        data = json.loads(result)
        assert "error" in data


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


class TestParseJson:
    def test_clean_json(self) -> None:
        result = _parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_array(self) -> None:
        result = _parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_markdown_fenced_json(self) -> None:
        text = "Here is the result:\n```json\n{\"valence\": 0.5}\n```"
        result = _parse_json(text)
        assert result == {"valence": 0.5}

    def test_markdown_fenced_no_language(self) -> None:
        text = "Result:\n```\n{\"key\": 42}\n```"
        result = _parse_json(text)
        assert result == {"key": 42}

    def test_preamble_text_before_json(self) -> None:
        text = "I analyzed the text and here is my response:\n\n{\"valence\": -0.3}"
        result = _parse_json(text)
        assert result == {"valence": -0.3}

    def test_preamble_with_array(self) -> None:
        text = 'Here are the facts:\n[{"content": "test", "importance": 5}]'
        result = _parse_json(text)
        assert result == [{"content": "test", "importance": 5}]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _parse_json("no json here at all")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _parse_json("")


class TestHelpers:
    def test_clamp_within_range(self) -> None:
        assert _clamp(0.5, 0.0, 1.0) == 0.5

    def test_clamp_below_min(self) -> None:
        assert _clamp(-2.0, -1.0, 1.0) == -1.0

    def test_clamp_above_max(self) -> None:
        assert _clamp(1.5, 0.0, 1.0) == 1.0

    def test_extract_task_marker(self) -> None:
        assert _extract_task_marker("[TASK:sentiment]\nText: hello") == "sentiment"
        assert _extract_task_marker("no marker") == "unknown"

    def test_extract_field(self) -> None:
        prompt = "Some preamble\nText: hello world\n\nMore stuff"
        assert _extract_field(prompt, "Text:") == "hello world"


# ---------------------------------------------------------------------------
# CognitiveProcessor with mock LLM
# ---------------------------------------------------------------------------


class TestCognitiveProcessorLLM:
    @pytest.mark.asyncio
    async def test_detect_sentiment_llm(self) -> None:
        engine = MockLLMEngine(responses={
            "sentiment": {"valence": 0.8, "arousal": 0.6, "label": "joy"},
        })
        processor = CognitiveProcessor(engine)
        result = await processor.detect_sentiment("I love this!")
        assert isinstance(result, SomaticMarker)
        assert result.valence == 0.8
        assert result.arousal == 0.6
        assert result.label == "joy"
        assert len(engine.calls) == 1
        assert "[TASK:sentiment]" in engine.calls[0]

    @pytest.mark.asyncio
    async def test_assess_significance_llm(self) -> None:
        engine = MockLLMEngine(responses={
            "significance": {
                "novelty": 0.9,
                "emotional_intensity": 0.7,
                "goal_relevance": 0.5,
                "reasoning": "test",
            },
        })
        processor = CognitiveProcessor(engine)
        interaction = Interaction(user_input="test", agent_output="reply")
        result = await processor.assess_significance(
            interaction, ["helpfulness"], ["recent chat"]
        )
        assert isinstance(result, SignificanceScore)
        assert result.novelty == 0.9
        assert result.emotional_intensity == 0.7

    @pytest.mark.asyncio
    async def test_extract_facts_llm(self) -> None:
        engine = MockLLMEngine(responses={
            "extract_facts": [
                {"content": "User's name is Bob", "importance": 9},
                {"content": "User likes Python", "importance": 7},
            ],
        })
        processor = CognitiveProcessor(engine)
        interaction = Interaction(
            user_input="My name is Bob and I like Python",
            agent_output="Nice to meet you!",
        )
        facts = await processor.extract_facts(interaction)
        assert len(facts) == 2
        assert all(isinstance(f, MemoryEntry) for f in facts)
        assert facts[0].content == "User's name is Bob"
        assert facts[0].type == MemoryType.SEMANTIC
        assert facts[0].importance == 9

    @pytest.mark.asyncio
    async def test_extract_entities_llm(self) -> None:
        engine = MockLLMEngine(responses={
            "extract_entities": [
                {"name": "Python", "type": "technology", "relation": "uses"},
            ],
        })
        processor = CognitiveProcessor(engine)
        interaction = Interaction(
            user_input="I use Python daily",
            agent_output="Great language!",
        )
        entities = await processor.extract_entities(interaction)
        assert len(entities) == 1
        assert entities[0]["name"] == "Python"
        assert entities[0]["type"] == "technology"

    @pytest.mark.asyncio
    async def test_reflect_llm(self) -> None:
        engine = MockLLMEngine(responses={
            "reflect": {
                "themes": ["coding", "debugging"],
                "summaries": [{"theme": "coding", "summary": "lots of Python", "importance": 8}],
                "promote": [],
                "emotional_patterns": "generally positive",
                "self_insight": "I help with code a lot",
            },
        })
        processor = CognitiveProcessor(engine)
        result = await processor.reflect(
            recent_episodes=[],
            current_self_model={"self_images": {}},
            soul_name="TestSoul",
        )
        assert isinstance(result, ReflectionResult)
        assert "coding" in result.themes
        assert result.self_insight == "I help with code a lot"

    @pytest.mark.asyncio
    async def test_reflect_heuristic_returns_none(self) -> None:
        processor = CognitiveProcessor(HeuristicEngine())
        result = await processor.reflect(
            recent_episodes=[],
            current_self_model={},
        )
        assert result is None


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


class TestFallback:
    @pytest.mark.asyncio
    async def test_failing_engine_falls_back_sentiment(self) -> None:
        processor = CognitiveProcessor(
            FailingEngine(),
            fallback=HeuristicEngine(),
        )
        result = await processor.detect_sentiment("I am very happy")
        assert isinstance(result, SomaticMarker)
        assert result.valence > 0  # heuristic should detect positive

    @pytest.mark.asyncio
    async def test_garbage_engine_falls_back_sentiment(self) -> None:
        processor = CognitiveProcessor(
            GarbageEngine(),
            fallback=HeuristicEngine(),
        )
        result = await processor.detect_sentiment("I am frustrated")
        assert isinstance(result, SomaticMarker)
        assert result.valence < 0  # heuristic should detect negative

    @pytest.mark.asyncio
    async def test_failing_engine_falls_back_significance(self) -> None:
        processor = CognitiveProcessor(
            FailingEngine(),
            fallback=HeuristicEngine(),
        )
        interaction = Interaction(user_input="test content", agent_output="reply")
        result = await processor.assess_significance(interaction, [], [])
        assert isinstance(result, SignificanceScore)

    @pytest.mark.asyncio
    async def test_failing_engine_no_fallback_returns_default(self) -> None:
        processor = CognitiveProcessor(FailingEngine())
        result = await processor.detect_sentiment("anything")
        assert isinstance(result, SomaticMarker)
        assert result.valence == 0.0
        assert result.label == "neutral"

    @pytest.mark.asyncio
    async def test_failing_engine_facts_with_extractor_fallback(self) -> None:
        def mock_extractor(interaction: Interaction) -> list[MemoryEntry]:
            return [
                MemoryEntry(
                    type=MemoryType.SEMANTIC,
                    content="fallback fact",
                    importance=5,
                )
            ]

        processor = CognitiveProcessor(
            FailingEngine(),
            fact_extractor=mock_extractor,
        )
        interaction = Interaction(user_input="test", agent_output="reply")
        facts = await processor.extract_facts(interaction)
        assert len(facts) == 1
        assert facts[0].content == "fallback fact"

    @pytest.mark.asyncio
    async def test_reflect_failing_engine_returns_none(self) -> None:
        processor = CognitiveProcessor(FailingEngine())
        result = await processor.reflect([], {})
        assert result is None


# ---------------------------------------------------------------------------
# Heuristic-only mode (identical to v0.2.0)
# ---------------------------------------------------------------------------


class TestHeuristicOnlyMode:
    @pytest.mark.asyncio
    async def test_sentiment_matches_v020(self) -> None:
        """Heuristic-only processor should call v0.2.0 detect_sentiment directly."""
        from soul_protocol.memory.sentiment import detect_sentiment

        processor = CognitiveProcessor(HeuristicEngine())
        text = "I am really excited about this project"
        result = await processor.detect_sentiment(text)
        expected = detect_sentiment(text)
        assert result.valence == expected.valence
        assert result.arousal == expected.arousal
        assert result.label == expected.label

    @pytest.mark.asyncio
    async def test_significance_matches_v020(self) -> None:
        """Heuristic-only processor should call v0.2.0 compute_significance."""
        from soul_protocol.memory.attention import compute_significance

        processor = CognitiveProcessor(HeuristicEngine())
        interaction = Interaction(
            user_input="I love building AI companions",
            agent_output="That sounds like a great project!",
        )
        values = ["helpfulness", "empathy"]
        recent = ["hello world", "how are you"]

        result = await processor.assess_significance(interaction, values, recent)
        expected = compute_significance(interaction, values, recent)
        assert result.novelty == expected.novelty
        assert result.emotional_intensity == expected.emotional_intensity
        assert result.goal_relevance == expected.goal_relevance


# ---------------------------------------------------------------------------
# Soul integration
# ---------------------------------------------------------------------------


class TestSoulIntegration:
    @pytest.mark.asyncio
    async def test_birth_with_engine(self) -> None:
        engine = MockLLMEngine(responses={
            "sentiment": {"valence": 0.5, "arousal": 0.3, "label": "joy"},
            "significance": {
                "novelty": 0.8, "emotional_intensity": 0.5,
                "goal_relevance": 0.4, "reasoning": "test",
            },
            "extract_facts": [],
            "extract_entities": [],
            "self_reflection": {
                "self_images": [],
                "insights": "",
                "relationship_notes": {},
            },
        })
        soul = await Soul.birth("TestSoul", engine=engine)
        assert soul.name == "TestSoul"

        # observe should use the LLM engine
        interaction = Interaction(
            user_input="Hello world",
            agent_output="Hi there!",
        )
        await soul.observe(interaction)
        assert len(engine.calls) >= 1  # engine was called

    @pytest.mark.asyncio
    async def test_birth_without_engine_works(self) -> None:
        """Default (no engine) should work identically to v0.2.0."""
        soul = await Soul.birth("TestSoul")
        interaction = Interaction(
            user_input="My name is Alice and I love Python",
            agent_output="Nice to meet you, Alice!",
        )
        await soul.observe(interaction)
        # Should not raise — heuristic mode works fine

    @pytest.mark.asyncio
    async def test_reflect_with_engine(self) -> None:
        engine = MockLLMEngine(responses={
            "reflect": {
                "themes": ["testing"],
                "summaries": [],
                "promote": [],
                "emotional_patterns": "neutral",
                "self_insight": "I help with tests",
            },
        })
        soul = await Soul.birth("TestSoul", engine=engine)
        result = await soul.reflect()
        assert isinstance(result, ReflectionResult)
        assert "testing" in result.themes

    @pytest.mark.asyncio
    async def test_reflect_without_engine_returns_none(self) -> None:
        soul = await Soul.birth("TestSoul")
        result = await soul.reflect()
        assert result is None

    @pytest.mark.asyncio
    async def test_full_observe_pipeline_with_llm(self) -> None:
        """Verify all observe steps use the LLM engine."""
        engine = MockLLMEngine(responses={
            "sentiment": {"valence": 0.9, "arousal": 0.7, "label": "excitement"},
            "significance": {
                "novelty": 0.9, "emotional_intensity": 0.8,
                "goal_relevance": 0.7, "reasoning": "very relevant",
            },
            "extract_facts": [
                {"content": "User is a developer", "importance": 7},
            ],
            "extract_entities": [
                {"name": "Python", "type": "technology", "relation": "uses"},
            ],
            "self_reflection": {
                "self_images": [{"domain": "technical_helper", "confidence": 0.8}],
                "insights": "helping with code",
                "relationship_notes": {"user": "developer"},
            },
        })
        soul = await Soul.birth(
            "TestSoul",
            values=["helpfulness"],
            engine=engine,
        )
        interaction = Interaction(
            user_input="I use Python for building AI tools",
            agent_output="That's awesome! Python is great for AI.",
        )
        await soul.observe(interaction)

        # Verify engine was called for each cognitive step
        task_markers = [_extract_task_marker(call) for call in engine.calls]
        assert "sentiment" in task_markers
        assert "significance" in task_markers
        assert "extract_facts" in task_markers
        assert "extract_entities" in task_markers
        assert "self_reflection" in task_markers


# ---------------------------------------------------------------------------
# Regression: _is_heuristic_only with explicit HeuristicEngine() pass
# ---------------------------------------------------------------------------


class TestHeuristicOnlyRegression:
    """When engine=HeuristicEngine() is passed explicitly, self-model domain
    discovery must use the heuristic path, not the LLM path.

    Previously, _is_heuristic_only required `fallback is None`, so passing
    engine=HeuristicEngine() with any fallback present (e.g. MemoryManager
    wraps it) set the flag False — routing update_self_model() through
    _self_reflection() which returns empty self_images → zero domains.
    """

    def test_explicit_heuristic_engine_sets_flag(self) -> None:
        """CognitiveProcessor with engine=HeuristicEngine() must be heuristic-only."""
        processor = CognitiveProcessor(HeuristicEngine())
        assert processor._is_heuristic_only is True

    def test_explicit_heuristic_engine_with_fallback_still_heuristic(self) -> None:
        """Even with a fallback present, HeuristicEngine primary → heuristic-only."""
        processor = CognitiveProcessor(
            HeuristicEngine(),
            fallback=HeuristicEngine(),
        )
        assert processor._is_heuristic_only is True

    def test_mock_llm_engine_is_not_heuristic_only(self) -> None:
        """Non-heuristic engine → flag must be False."""
        processor = CognitiveProcessor(MockLLMEngine())
        assert processor._is_heuristic_only is False

    @pytest.mark.asyncio
    async def test_explicit_heuristic_engine_produces_domains(self) -> None:
        """Soul.birth(engine=HeuristicEngine()) must discover domains from interactions.

        Regression for the bug where zero domains were discovered when
        engine=HeuristicEngine() was passed explicitly to Soul.birth().
        """
        soul = await Soul.birth(
            "RegressionSoul",
            values=["helpfulness", "curiosity"],
        )

        # Simulate topical interactions that heuristic self-model can classify
        topics = [
            ("I love writing Python code", "Python is great for many tasks"),
            ("Can you help me debug this function?", "Sure, let me look at it"),
            ("I use Python for data analysis too", "pandas and numpy are great"),
            ("I enjoy solving coding puzzles", "That's a great way to learn"),
            ("My favorite language is Python", "It has a great ecosystem"),
        ]
        for user_input, agent_output in topics:
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output)
            )

        # With the bug: 0 domains. With the fix: ≥1 domain discovered.
        domains = soul.self_model.get_active_self_images()
        assert len(domains) >= 1, (
            f"Expected ≥1 domain after {len(topics)} topical interactions, "
            f"got 0. This indicates _is_heuristic_only=False (the bug)."
        )

    @pytest.mark.asyncio
    async def test_heuristic_engine_none_produces_same_domains(self) -> None:
        """Soul.birth() with no engine must produce the same results as explicit HeuristicEngine()."""
        interactions = [
            Interaction(
                user_input="I love writing Python code",
                agent_output="Python is a wonderful language",
            ),
            Interaction(
                user_input="Can you help me debug this loop?",
                agent_output="Sure, let me trace through it",
            ),
            Interaction(
                user_input="My main interest is machine learning",
                agent_output="That's a fascinating field",
            ),
        ]

        # Default (engine=None): heuristic path via Soul internals
        soul_default = await Soul.birth("DefaultSoul", values=["curiosity"])
        for interaction in interactions:
            await soul_default.observe(interaction)

        # Explicit HeuristicEngine: must take the same path
        soul_explicit = await Soul.birth(
            "ExplicitSoul",
            values=["curiosity"],
            engine=HeuristicEngine(),
        )
        for interaction in interactions:
            await soul_explicit.observe(interaction)

        default_domains = {img.domain for img in soul_default.self_model.get_active_self_images()}
        explicit_domains = {img.domain for img in soul_explicit.self_model.get_active_self_images()}

        # Both should discover the same domains from the same input
        assert default_domains == explicit_domains, (
            f"Default and explicit HeuristicEngine paths diverged.\n"
            f"Default: {default_domains}\nExplicit: {explicit_domains}"
        )
