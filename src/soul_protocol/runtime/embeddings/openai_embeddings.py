# embeddings/openai_embeddings.py — OpenAI embedding provider.
# Created: 2026-03-22 — Real semantic embeddings via OpenAI's embedding API.
# Default model: text-embedding-3-small (1536-dim).
# API key sourced from OPENAI_API_KEY env var. Includes retry with backoff.

from __future__ import annotations

import os
import time

# Model name → known dimension count (avoids a probe call when possible)
_KNOWN_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Retry settings
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class OpenAIEmbeddingProvider:
    """Embedding provider using the OpenAI embeddings API.

    Produces high-quality semantic embeddings via OpenAI's hosted models.
    Requires an ``OPENAI_API_KEY`` environment variable (or pass it directly).

    Includes automatic retry with exponential backoff for rate-limit and
    transient errors.

    Args:
        model: OpenAI model identifier. Default: ``text-embedding-3-small``.
        api_key: OpenAI API key. Falls back to ``OPENAI_API_KEY`` env var.
        max_retries: Maximum number of retry attempts. Default: 3.
        base_delay: Initial retry delay in seconds. Default: 1.0.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        max_retries: int = _MAX_RETRIES,
        base_delay: float = _BASE_DELAY,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._client: object | None = None
        self._dimensions: int | None = _KNOWN_DIMENSIONS.get(model)

    def _get_client(self) -> object:
        """Lazily create the OpenAI client on first use."""
        if self._client is not None:
            return self._client

        if not self._api_key:
            raise ValueError(
                "OpenAI API key is required. Set the OPENAI_API_KEY environment "
                "variable or pass api_key to OpenAIEmbeddingProvider."
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAIEmbeddingProvider. "
                "Install it with: pip install 'soul-protocol[embeddings-openai]'"
            ) from None

        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call the OpenAI embeddings API with retry logic.

        Args:
            texts: Batch of texts to embed.

        Returns:
            List of embedding vectors in input order.

        Raises:
            Exception: After exhausting retries.
        """
        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = client.embeddings.create(input=texts, model=self._model)
                # Sort by index to guarantee input order
                data = sorted(response.data, key=lambda d: d.index)
                vectors = [d.embedding for d in data]

                # Learn dimensions from first successful response
                if self._dimensions is None and vectors:
                    self._dimensions = len(vectors[0])

                return vectors
            except Exception as exc:
                last_error = exc
                # Check for rate-limit or transient error
                status = getattr(exc, "status_code", None)
                if status is not None and status not in (429, 500, 502, 503, 504):
                    raise
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2**attempt)
                    time.sleep(delay)

        raise last_error  # type: ignore[misc]

    @property
    def dimensions(self) -> int:
        """Dimensionality of the embedding vectors."""
        if self._dimensions is not None:
            return self._dimensions
        # For unknown models, do a probe call
        self._call_api(["probe"])
        assert self._dimensions is not None
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        """Embed a single text via the OpenAI API.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats with length == self.dimensions.
        """
        vectors = self._call_api([text])
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []
        return self._call_api(texts)
