---
{
  "title": "Test Suite for TF-IDF Embedder",
  "summary": "Validates the TFIDFEmbedder class, which converts text into fixed-length float vectors using term-frequency/inverse-document-frequency weighting. Tests cover the fit/embed lifecycle, semantic similarity behavior, edge cases for unfitted state, and batch consistency.",
  "concepts": [
    "TF-IDF",
    "embedder",
    "text embedding",
    "corpus",
    "vocabulary",
    "semantic similarity",
    "memory recall",
    "fit embed",
    "normalization",
    "dimensions"
  ],
  "categories": [
    "testing",
    "embeddings",
    "natural language processing",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "09fe0c27ab17ce49"
  ],
  "backlinks": null,
  "word_count": 528,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_tfidf_embedder.py` tests `soul_protocol.runtime.embeddings.tfidf_embedder.TFIDFEmbedder` — the semantic text-to-vector converter used by the memory recall layer. Unlike the hash-based embedder (which is deterministic but not semantic), TF-IDF captures term importance relative to a corpus, letting the system distinguish between rare and common words. This matters for memory recall: a query for "childhood" should rank episodic memories about childhood higher than memories that happen to mention common words.

## Two-Phase Contract: fit() then embed()

The embedder follows a strict two-phase design:

1. **`fit(corpus)`** — builds a vocabulary and computes IDF weights from a list of training documents.
2. **`embed(text)`** — converts a string to a vector using the fitted vocabulary.

Calling `embed()` before `fit()` must return a zero vector, not raise an exception. This is a defensive design: when a fresh soul has no corpus yet, any recall attempt should gracefully return "no results" rather than crash.

```python
def test_unfitted_returns_zero_vector(self) -> None:
    embedder = TFIDFEmbedder()
    vec = embedder.embed("hello world")
    assert all(x == 0.0 for x in vec)
```

## Test Groups

### `TestTFIDFEmbedderBasics`
Confirms the construction contract:
- Default dimensions are 128 (a balance between expressiveness and overhead for the typical soul corpus size).
- Custom dimensions can be set, which is important for memory-constrained deployments.
- `fitted` flag starts `False` and becomes `True` after any `fit()` call, even on an empty corpus.

### `TestTFIDFEmbedderFit`
- **Empty corpus fit** — after fitting on `[]`, `embed()` must still return an all-zero vector. This prevents an uninitialized-state crash if the corpus is built lazily.
- **Vocabulary construction** — after fitting on real text, embedding corpus terms must produce non-zero vectors, confirming that the vocabulary was actually populated.
- **Dimension capping** — `TFIDFEmbedder(dimensions=5)` fitted on a 15-term corpus must produce 5-element vectors, confirming the dimensionality reduction works.

### `TestTFIDFEmbedderEmbed`
- **Output length** must always equal the configured `dimensions`, regardless of text content.
- **Normalized output** — the L2 norm of a non-zero embedding must be `1.0` (within floating-point tolerance). Normalization is required so that cosine similarity scores are comparable across memories of different lengths.
- **Empty and unknown-term inputs** return zero vectors gracefully.

### `TestTFIDFEmbedderSimilarity`
This is the most important group: it validates that the embedder produces *semantically meaningful* vectors, not just syntactically correct ones.

```python
def test_similar_topics_high_similarity(self, fitted_embedder) -> None:
    # "dog training" and "puppy obedience" share semantic space
    ...
def test_different_topics_low_similarity(self, fitted_embedder) -> None:
    # "cooking recipes" vs "space exploration" should be dissimilar
    ...
```

The `fitted_embedder` fixture pre-trains on a diverse corpus so these comparisons are meaningful.

### `TestTFIDFEmbedderBatch`
- **Batch consistency** — embedding a list must produce the same result as embedding each item individually. This prevents subtle bugs where batch processing shares state across calls.
- **Empty batch** returns an empty list without raising.

## Data Flow

```
Soul.remember(text)
    → TFIDFEmbedder.fit(existing_memories)  # lazily or at index time
    → TFIDFEmbedder.embed(text)             # produces [float, ...]
    → VectorSearchStrategy.index()          # stored in memory index
    → VectorSearchStrategy.search(query)    # ranked by cosine_similarity
```

## Known Gaps

No TODO/FIXME markers. Property-based testing of the TF-IDF scoring formula itself (e.g., asserting that rarer terms produce higher IDF weights) is not present — the suite tests behavior from the outside but not the internal weighting math.
