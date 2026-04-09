# adapters/ollama.py — OllamaEngine: CognitiveEngine backed by a local Ollama server.
# Created: feat/cognitive-adapters — uses httpx (already a core dep) so no extra install needed.
#   Communicates with Ollama's REST API directly. POST /api/generate with stream=False.

from __future__ import annotations


class OllamaEngine:
    """CognitiveEngine backed by a local Ollama server.

    Uses ``httpx`` (already in soul-protocol's core deps) — no additional
    package install required.

    Usage::

        from soul_protocol.runtime.cognitive.adapters import OllamaEngine
        from soul_protocol import Soul

        soul = await Soul.birth(name="Aria", engine=OllamaEngine(model="llama3.2"))

    The Ollama server must be running at ``host`` (default: http://localhost:11434).
    Start it with ``ollama serve`` and pull the model with ``ollama pull llama3.2``.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")

    async def think(self, prompt: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "OllamaEngine requires the 'httpx' package. Install it with: pip install httpx"
            ) from exc

        url = f"{self._host}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
