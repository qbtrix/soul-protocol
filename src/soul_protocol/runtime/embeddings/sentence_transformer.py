# embeddings/sentence_transformer.py — SentenceTransformer embedding provider.
# Created: 2026-03-22 — Real semantic embeddings using sentence-transformers library.
# Default model: all-MiniLM-L6-v2 (384-dim, fast, good quality).
# Lazy model loading — model is not loaded until the first embed() call.

from __future__ import annotations


class SentenceTransformerProvider:
    """Embedding provider using the sentence-transformers library.

    Produces real semantic embeddings where similar texts yield similar
    vectors. Uses lazy model loading to avoid importing the heavy
    sentence-transformers library until the first embed() call.

    Args:
        model_name: HuggingFace model identifier.
            Default: ``all-MiniLM-L6-v2`` (384-dim, fast).
        device: Torch device string (``cpu``, ``cuda``, ``mps``).
            Default: ``None`` (auto-detect).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model: object | None = None
        self._dimensions: int | None = None

    def _load_model(self) -> None:
        """Lazily load the sentence-transformers model on first use."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerProvider. "
                "Install it with: pip install 'soul-protocol[embeddings-st]'"
            ) from None

        kwargs: dict = {}
        if self._device is not None:
            kwargs["device"] = self._device

        self._model = SentenceTransformer(self._model_name, **kwargs)
        # Determine dimensions from a probe embedding
        probe = self._model.encode(["probe"], convert_to_numpy=True)
        self._dimensions = int(probe.shape[1])

    @property
    def dimensions(self) -> int:
        """Dimensionality of the embedding vectors."""
        self._load_model()
        assert self._dimensions is not None
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a semantic vector.

        Args:
            text: The input text to embed.

        Returns:
            A normalized list of floats with length == self.dimensions.
        """
        self._load_model()
        assert self._model is not None

        vector = self._model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return vector[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently in a single batch.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        self._load_model()
        assert self._model is not None

        vectors = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [row.tolist() for row in vectors]
