# adapters/_auto.py — engine_from_env(): auto-detect best available CognitiveEngine.
# Created: feat/cognitive-adapters — scans environment variables for known API keys and
#   returns the most capable engine available. Priority: Anthropic → OpenAI → Ollama → Heuristic.

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine


def engine_from_env() -> CognitiveEngine:
    """Auto-detect the best available CognitiveEngine from the environment.

    Priority order:
      1. ``ANTHROPIC_API_KEY`` → AnthropicEngine (claude-haiku-4-5-20251001)
      2. ``OPENAI_API_KEY`` → OpenAIEngine (gpt-4o-mini)
      3. ``OLLAMA_HOST`` → OllamaEngine (llama3.2 at the configured host)
      4. No env vars → HeuristicEngine (zero-dependency fallback)

    Returns:
        A CognitiveEngine instance ready to use with Soul.birth() or Soul.awaken().

    Example::

        from soul_protocol.runtime.cognitive.adapters import engine_from_env
        from soul_protocol import Soul

        # Automatically picks up whichever LLM is configured in the environment
        soul = await Soul.birth(name="Aria", engine=engine_from_env())
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from soul_protocol.runtime.cognitive.adapters.anthropic import AnthropicEngine

            return AnthropicEngine()
        except ImportError:
            pass  # anthropic package not installed; try next

    if os.environ.get("OPENAI_API_KEY"):
        try:
            from soul_protocol.runtime.cognitive.adapters.openai import OpenAIEngine

            return OpenAIEngine()
        except ImportError:
            pass  # openai package not installed; try next

    if os.environ.get("OLLAMA_HOST"):
        from soul_protocol.runtime.cognitive.adapters.ollama import OllamaEngine

        return OllamaEngine(host=os.environ["OLLAMA_HOST"])

    # Final fallback — always available, zero deps
    from soul_protocol.runtime.cognitive.engine import HeuristicEngine

    return HeuristicEngine()
