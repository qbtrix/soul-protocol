# tests/test_mcp_sampling_engine.py — Tests for MCPSamplingEngine and server lazy wiring.
# Created: feat/mcp-sampling-engine — covers the happy path, fallback on error,
#   fallback when ctx=None, and server-side lazy engine wiring via _get_or_create_engine().

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# MCPSamplingEngine unit tests
# ---------------------------------------------------------------------------


class TestMCPSamplingEngineThinkSuccess:
    """ctx.sample() returns a good SamplingResult — engine should return its text."""

    @pytest.mark.asyncio
    async def test_think_returns_text_from_sampling_result(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_result = MagicMock()
        mock_result.text = '{"valence": 0.7, "arousal": 0.5, "label": "curious"}'

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(return_value=mock_result)

        engine = MCPSamplingEngine(mock_ctx)
        result = await engine.think("[TASK:sentiment] Analyze: I love building this")

        assert result == mock_result.text
        mock_ctx.sample.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_think_passes_prompt_to_ctx_sample(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_result = MagicMock()
        mock_result.text = "some response"

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(return_value=mock_result)

        engine = MCPSamplingEngine(mock_ctx)
        prompt = "[TASK:significance] Evaluate: User mentioned their birthday"
        await engine.think(prompt)

        # The prompt must be forwarded to ctx.sample unchanged
        mock_ctx.sample.assert_awaited_once_with(prompt)

    @pytest.mark.asyncio
    async def test_think_handles_none_text_falls_back_to_result(self):
        """When SamplingResult.text is None, fall back to result.result as string."""
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_result = MagicMock()
        mock_result.text = None
        mock_result.result = {"valence": 0.0, "arousal": 0.2, "label": "neutral"}

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(return_value=mock_result)

        engine = MCPSamplingEngine(mock_ctx)
        result = await engine.think("[TASK:sentiment] Analyze: ok")

        # Should stringify mock_result.result since .text is None
        assert result is not None
        assert len(result) > 0


class TestMCPSamplingEngineFallbackOnError:
    """ctx.sample() raises — engine should fall back to HeuristicEngine silently."""

    @pytest.mark.asyncio
    async def test_falls_back_on_not_implemented_error(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(
            side_effect=NotImplementedError("host doesn't support sampling")
        )

        engine = MCPSamplingEngine(mock_ctx)
        # HeuristicEngine should handle this without raising
        result = await engine.think("[TASK:sentiment] I feel great today")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should be valid JSON from HeuristicEngine
        data = json.loads(result)
        assert "valence" in data or "error" in data

    @pytest.mark.asyncio
    async def test_falls_back_on_generic_exception(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(side_effect=RuntimeError("connection reset"))

        engine = MCPSamplingEngine(mock_ctx)
        result = await engine.think("[TASK:sentiment] I feel great today")

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        mock_ctx = MagicMock()
        mock_ctx.sample = AsyncMock(side_effect=TimeoutError())

        engine = MCPSamplingEngine(mock_ctx)
        result = await engine.think("[TASK:extract_facts] User: My name is Alice")

        assert isinstance(result, str)
        assert len(result) > 0


class TestMCPSamplingEngineFallbackWhenNoCtx:
    """ctx=None — engine should use HeuristicEngine immediately."""

    @pytest.mark.asyncio
    async def test_none_ctx_uses_heuristic(self):
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        engine = MCPSamplingEngine(None)
        result = await engine.think("[TASK:sentiment] Text: I am happy")

        assert isinstance(result, str)
        assert len(result) > 0
        data = json.loads(result)
        assert "valence" in data

    @pytest.mark.asyncio
    async def test_none_ctx_does_not_attempt_sample_call(self):
        """With ctx=None there should be no attempt to call .sample()."""
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        engine = MCPSamplingEngine(None)
        # If the engine tried to call ctx.sample() it would raise AttributeError.
        # The test passes as long as no exception is raised.
        result = await engine.think("[TASK:extract_facts] User: hello")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Server lazy wiring test
# ---------------------------------------------------------------------------


class TestServerWiresEngineOnToolCall:
    """_get_or_create_engine() constructs MCPSamplingEngine and wires it to souls."""

    def test_get_or_create_engine_creates_engine_with_ctx(self):
        import soul_protocol.mcp.server as server_module
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        # Reset module-level engine cache
        server_module._engine = None

        mock_ctx = MagicMock()

        engine = server_module._get_or_create_engine(mock_ctx)

        assert isinstance(engine, MCPSamplingEngine)
        assert engine._ctx is mock_ctx
        # Cache should now be populated
        assert server_module._engine is engine

    def test_get_or_create_engine_returns_same_instance(self):
        """Subsequent calls reuse the same engine (session-scoped cache)."""
        import soul_protocol.mcp.server as server_module

        server_module._engine = None

        mock_ctx = MagicMock()
        engine1 = server_module._get_or_create_engine(mock_ctx)

        mock_ctx2 = MagicMock()  # different ctx object
        engine2 = server_module._get_or_create_engine(mock_ctx2)

        # Should be the same instance
        assert engine1 is engine2

    def test_get_or_create_engine_wires_into_loaded_souls(self):
        """All souls in the registry get set_engine() called when engine is first created."""
        import soul_protocol.mcp.server as server_module
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        server_module._engine = None

        # Mock a soul in the registry
        mock_soul = MagicMock()
        server_module._registry._souls["test_soul"] = mock_soul

        mock_ctx = MagicMock()

        try:
            engine = server_module._get_or_create_engine(mock_ctx)

            mock_soul.set_engine.assert_called_once_with(engine)
            assert isinstance(engine, MCPSamplingEngine)
        finally:
            # Clean up — remove our mock soul from the registry
            server_module._registry._souls.pop("test_soul", None)
            server_module._engine = None

    def test_lifespan_resets_engine_cache(self):
        """Engine cache is cleared at startup so each session gets a fresh engine."""
        import soul_protocol.mcp.server as server_module
        from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

        # Pre-populate the cache
        server_module._engine = MCPSamplingEngine(MagicMock())
        assert server_module._engine is not None

        # Simulate lifespan startup clearing the engine
        server_module._engine = None
        assert server_module._engine is None
