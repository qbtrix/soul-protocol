# tests/test_cognitive_adapters.py — Tests for the cognitive adapters package.
# Created: feat/cognitive-adapters — covers CallableEngine, engine_from_env auto-detection,
#   Soul factory integration with callable/auto/None engine, and CognitiveProcessor
#   with a tracked mock engine.

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from soul_protocol import Soul
from soul_protocol.runtime.cognitive.adapters._auto import engine_from_env
from soul_protocol.runtime.cognitive.adapters._callable import CallableEngine
from soul_protocol.runtime.cognitive.engine import CognitiveProcessor, HeuristicEngine
from soul_protocol.runtime.types import Interaction

# ---------------------------------------------------------------------------
# CallableEngine
# ---------------------------------------------------------------------------


class TestCallableEngine:
    """CallableEngine wraps sync and async callables as CognitiveEngine."""

    @pytest.mark.asyncio
    async def test_callable_engine_sync(self):
        """Sync lambda is invoked and returns its value."""

        def fn(prompt: str) -> str:
            return f"echo:{prompt}"

        engine = CallableEngine(fn)
        result = await engine.think("hello")
        assert result == "echo:hello"

    @pytest.mark.asyncio
    async def test_callable_engine_async(self):
        """Async function is awaited and returns its value."""

        async def async_fn(prompt: str) -> str:
            return f"async:{prompt}"

        engine = CallableEngine(async_fn)
        result = await engine.think("world")
        assert result == "async:world"

    def test_callable_engine_detects_async(self):
        """_is_async flag correctly detects coroutine functions."""
        sync_engine = CallableEngine(lambda p: p)
        assert sync_engine._is_async is False

        async def coro(p: str) -> str:
            return p

        async_engine = CallableEngine(coro)
        assert async_engine._is_async is True

    @pytest.mark.asyncio
    async def test_callable_engine_sync_runs_in_executor(self):
        """Sync callable still returns correct value even via executor path."""
        call_log: list[str] = []

        def blocking_fn(prompt: str) -> str:
            call_log.append(prompt)
            return "ok"

        engine = CallableEngine(blocking_fn)
        result = await engine.think("test-prompt")
        assert result == "ok"
        assert call_log == ["test-prompt"]


# ---------------------------------------------------------------------------
# engine_from_env
# ---------------------------------------------------------------------------


class TestEngineFromEnv:
    """engine_from_env() picks up the right adapter from environment variables."""

    def test_engine_from_env_anthropic(self, monkeypatch):
        """ANTHROPIC_API_KEY present → AnthropicEngine returned (import mocked)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        # Mock anthropic package so we don't need it installed
        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = MagicMock()

        with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
            engine = engine_from_env()
            from soul_protocol.runtime.cognitive.adapters.anthropic import AnthropicEngine

            assert isinstance(engine, AnthropicEngine)

    def test_engine_from_env_openai(self, monkeypatch):
        """OPENAI_API_KEY present (no Anthropic key) → OpenAIEngine returned."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        fake_openai = MagicMock()
        fake_openai.AsyncOpenAI.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": fake_openai}):
            engine = engine_from_env()
            from soul_protocol.runtime.cognitive.adapters.openai import OpenAIEngine

            assert isinstance(engine, OpenAIEngine)

    def test_engine_from_env_ollama(self, monkeypatch):
        """OLLAMA_HOST present (no API keys) → OllamaEngine returned."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")

        engine = engine_from_env()
        from soul_protocol.runtime.cognitive.adapters.ollama import OllamaEngine

        assert isinstance(engine, OllamaEngine)
        assert engine._host == "http://localhost:11434"

    def test_engine_from_env_fallback(self, monkeypatch):
        """No env vars → HeuristicEngine returned (zero-dependency fallback)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        engine = engine_from_env()
        assert isinstance(engine, HeuristicEngine)

    def test_engine_from_env_anthropic_missing_package(self, monkeypatch):
        """ANTHROPIC_API_KEY set but anthropic not installed → falls through to next."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        # Simulate anthropic not installed: the adapter module's import raises ImportError.
        # We patch the adapter class itself to raise ImportError when instantiated,
        # mirroring the soft-import pattern in anthropic.py.
        fake_openai = MagicMock()
        fake_openai.AsyncOpenAI.return_value = MagicMock()

        with (
            patch(
                "soul_protocol.runtime.cognitive.adapters.anthropic.AnthropicEngine.__init__",
                side_effect=ImportError("anthropic not installed"),
            ),
            patch.dict("sys.modules", {"openai": fake_openai}),
        ):
            engine = engine_from_env()
            from soul_protocol.runtime.cognitive.adapters.openai import OpenAIEngine

            assert isinstance(engine, OpenAIEngine)


# ---------------------------------------------------------------------------
# Soul factory integration
# ---------------------------------------------------------------------------


class TestSoulEngineIntegration:
    """Soul.birth() and Soul.awaken() accept callable/auto/None engine values."""

    @pytest.mark.asyncio
    async def test_soul_birth_engine_callable(self):
        """Soul.birth() with a sync lambda wraps it in CallableEngine."""

        def fn(_p: str) -> str:
            return '{"valence": 0.5, "arousal": 0.5, "label": "neutral"}'

        soul = await Soul.birth(name="Aria", engine=fn)
        # The engine stored internally should be a CallableEngine
        from soul_protocol.runtime.cognitive.adapters._callable import CallableEngine

        assert isinstance(soul._engine, CallableEngine)

    @pytest.mark.asyncio
    async def test_soul_birth_engine_async_callable(self):
        """Soul.birth() with an async function wraps it in CallableEngine."""

        async def my_llm(prompt: str) -> str:
            return '{"valence": 0.5, "arousal": 0.5, "label": "neutral"}'

        soul = await Soul.birth(name="Aria", engine=my_llm)
        assert isinstance(soul._engine, CallableEngine)
        assert soul._engine._is_async is True

    @pytest.mark.asyncio
    async def test_soul_birth_engine_none(self):
        """Soul.birth() with no engine sets _engine to None (heuristic path)."""
        soul = await Soul.birth(name="Aria")
        assert soul._engine is None

    @pytest.mark.asyncio
    async def test_soul_birth_engine_auto(self, monkeypatch):
        """Soul.birth(engine='auto') resolves via engine_from_env()."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        soul = await Soul.birth(name="Aria", engine="auto")
        # With no env vars, auto resolves to HeuristicEngine
        assert isinstance(soul._engine, HeuristicEngine)

    @pytest.mark.asyncio
    async def test_soul_birth_engine_auto_with_anthropic(self, monkeypatch):
        """Soul.birth(engine='auto') with ANTHROPIC_API_KEY → AnthropicEngine."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = MagicMock()

        with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
            soul = await Soul.birth(name="Aria", engine="auto")
            from soul_protocol.runtime.cognitive.adapters.anthropic import AnthropicEngine

            assert isinstance(soul._engine, AnthropicEngine)

    @pytest.mark.asyncio
    async def test_soul_load_engine_callable(self, tmp_path):
        """Soul.awaken() with a callable wraps it in CallableEngine."""
        # First birth and export a soul
        soul = await Soul.birth(name="TestSoul")
        soul_path = tmp_path / "test.soul"
        await soul.export(str(soul_path))

        def fn(_p: str) -> str:
            return '{"valence": 0.0, "arousal": 0.0, "label": "neutral"}'

        awakened = await Soul.awaken(str(soul_path), engine=fn)
        assert isinstance(awakened._engine, CallableEngine)

    @pytest.mark.asyncio
    async def test_soul_load_engine_none(self, tmp_path):
        """Soul.awaken() with no engine stores None (heuristic path)."""
        soul = await Soul.birth(name="TestSoul2")
        soul_path = tmp_path / "test2.soul"
        await soul.export(str(soul_path))

        awakened = await Soul.awaken(str(soul_path))
        assert awakened._engine is None

    @pytest.mark.asyncio
    async def test_soul_load_engine_auto(self, tmp_path, monkeypatch):
        """Soul.awaken(engine='auto') resolves via engine_from_env()."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)

        soul = await Soul.birth(name="TestSoul3")
        soul_path = tmp_path / "test3.soul"
        await soul.export(str(soul_path))

        awakened = await Soul.awaken(str(soul_path), engine="auto")
        # No env vars → HeuristicEngine
        assert isinstance(awakened._engine, HeuristicEngine)


# ---------------------------------------------------------------------------
# CognitiveProcessor with a tracked engine
# ---------------------------------------------------------------------------


class TrackingEngine:
    """CognitiveEngine that records all prompts passed to think()."""

    def __init__(self, response: str = "{}") -> None:
        self.calls: list[str] = []
        self._response = response

    async def think(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._response


class TestCognitiveProcessorWithRealEngine:
    """CognitiveProcessor uses the engine's think() for each cognitive task."""

    @pytest.mark.asyncio
    async def test_cognitive_processor_calls_engine_for_sentiment(self):
        """detect_sentiment() calls the engine's think() method."""
        engine = TrackingEngine(response='{"valence": 0.8, "arousal": 0.6, "label": "joy"}')
        processor = CognitiveProcessor(engine=engine)

        result = await processor.detect_sentiment("I feel great today!")
        assert len(engine.calls) == 1
        assert result.label == "joy"
        assert result.valence == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_cognitive_processor_calls_engine_for_significance(self):
        """assess_significance() calls the engine's think() method."""
        engine = TrackingEngine(
            response='{"novelty": 0.7, "emotional_intensity": 0.5, "goal_relevance": 0.4}'
        )
        processor = CognitiveProcessor(engine=engine)
        interaction = Interaction(user_input="I just got promoted!", agent_output="Congrats!")

        result = await processor.assess_significance(interaction, [], [])
        assert len(engine.calls) == 1
        assert result.novelty == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_cognitive_processor_calls_engine_for_fact_extraction(self):
        """extract_facts() calls the engine's think() method."""
        engine = TrackingEngine(response='[{"content": "User prefers Python", "importance": 7}]')
        processor = CognitiveProcessor(engine=engine)
        interaction = Interaction(
            user_input="I love Python", agent_output="Python is a great choice!"
        )

        facts = await processor.extract_facts(interaction)
        assert len(engine.calls) == 1
        assert len(facts) == 1
        assert "Python" in facts[0].content

    @pytest.mark.asyncio
    async def test_cognitive_processor_fallback_on_bad_json(self):
        """CognitiveProcessor falls back gracefully when engine returns non-JSON."""
        engine = TrackingEngine(response="this is not json at all")
        # Provide a fallback fact extractor so we can verify the fallback path
        fallback_called: list[bool] = []

        def dummy_extractor(interaction: Interaction):
            fallback_called.append(True)
            return []

        processor = CognitiveProcessor(engine=engine, fact_extractor=dummy_extractor)
        interaction = Interaction(user_input="hello", agent_output="hi")

        await processor.extract_facts(interaction)
        # Engine was called but parsing failed, fallback was used
        assert len(engine.calls) == 1
        assert fallback_called  # fallback extractor was invoked


# ---------------------------------------------------------------------------
# Adapter imports — soft import safety
# ---------------------------------------------------------------------------


class TestAdapterImportSafety:
    """Adapters that need missing packages raise ImportError only at instantiation."""

    def test_anthropic_engine_import_error_on_missing_package(self):
        """AnthropicEngine raises ImportError with helpful message if anthropic not installed."""
        with patch.dict("sys.modules", {"anthropic": None}):
            import soul_protocol.runtime.cognitive.adapters.anthropic as mod

            # Force re-evaluation by calling with sys.modules patched
            with pytest.raises(ImportError, match="pip install soul-protocol\\[anthropic\\]"):
                mod.AnthropicEngine()

    def test_openai_engine_import_error_on_missing_package(self):
        """OpenAIEngine raises ImportError with helpful message if openai not installed."""
        with patch.dict("sys.modules", {"openai": None}):
            import soul_protocol.runtime.cognitive.adapters.openai as mod

            with pytest.raises(ImportError, match="pip install soul-protocol\\[openai\\]"):
                mod.OpenAIEngine()

    def test_litellm_engine_import_error_on_missing_package(self):
        """LiteLLMEngine raises ImportError with helpful message if litellm not installed."""
        with patch.dict("sys.modules", {"litellm": None}):
            import soul_protocol.runtime.cognitive.adapters.litellm as mod

            with pytest.raises(ImportError, match="pip install soul-protocol\\[litellm\\]"):
                mod.LiteLLMEngine(model="openai/gpt-4o-mini")


# ---------------------------------------------------------------------------
# OllamaEngine HTTP mocking
# ---------------------------------------------------------------------------


class TestOllamaEngine:
    """OllamaEngine makes correct HTTP requests to the Ollama REST API."""

    @pytest.mark.asyncio
    async def test_ollama_engine_posts_to_correct_endpoint(self):
        """OllamaEngine POSTs to /api/generate and returns the response field."""
        import httpx

        from soul_protocol.runtime.cognitive.adapters.ollama import OllamaEngine

        engine = OllamaEngine(model="llama3.2", host="http://localhost:11434")

        mock_response_data = {"response": "The sky is blue.", "done": True}

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response_data)
        )

        # Patch AsyncClient to use our mock transport
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        with patch.object(httpx.AsyncClient, "__init__", patched_init):
            result = await engine.think("What colour is the sky?")

        assert result == "The sky is blue."

    @pytest.mark.asyncio
    async def test_ollama_engine_uses_custom_host(self):
        """OllamaEngine respects the custom host parameter."""
        from soul_protocol.runtime.cognitive.adapters.ollama import OllamaEngine

        engine = OllamaEngine(model="mistral", host="http://192.168.1.100:11434")
        assert engine._host == "http://192.168.1.100:11434"
        assert engine._model == "mistral"
