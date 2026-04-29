---
{
  "title": "Hash Embedder: Deterministic Pseudo-Embeddings for Testing",
  "summary": "The `HashEmbedder` produces deterministic fixed-length vectors from text using character n-gram hashing — no external dependencies, no model downloads, same input always yields the same output. It is intentionally non-semantic (similar texts do not produce similar vectors) and exists solely to enable embedding pipeline tests without requiring real embedding backends.",
  "concepts": [
    "HashEmbedder",
    "deterministic embeddings",
    "n-gram hashing",
    "MD5",
    "L2 normalization",
    "testing utility",
    "EmbeddingProvider",
    "character n-grams",
    "bucket hashing",
    "cosine similarity"
  ],
  "categories": [
    "embeddings",
    "testing",
    "memory search"
  ],
  "source_docs": [
    "7d3cd1ceae872233"
  ],
  "backlinks": null,
  "word_count": 419,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Testing code that uses embeddings normally requires either mocking the embedding layer or installing a real model. Both approaches have costs: mocks can mask real interface bugs, and models add setup friction and non-determinism.

`HashEmbedder` offers a third path: a deterministic, dependency-free embedder that satisfies the `EmbeddingProvider` protocol and produces real float vectors from real inputs — just without semantic meaning. Tests can verify that the pipeline wires up correctly, that indexing works, that threshold filtering applies, and that batch operations return the right shape, all without a live model.

## How It Works

### Character N-gram Extraction

```python
def _extract_ngrams(self, text: str) -> list[str]:
    ngrams = []
    for i in range(len(text) - self._ngram_size + 1):
        ngrams.append(text[i : i + self._ngram_size])
    words = text.split()
    ngrams.extend(words)  # whole words as bonus features
    return ngrams
```

The default `ngram_size=3` extracts overlapping character trigrams (e.g., "hello" → "hel", "ell", "llo"). Whole words are appended as additional features to improve bucket distribution — without them, short texts with few unique trigrams would produce very sparse vectors.

### Hashing into Buckets

Each n-gram is MD5-hashed. The first 4 bytes determine which dimension (bucket) the n-gram contributes to; the next 4 bytes provide the value accumulated in that bucket:

```python
h = hashlib.md5(ngram.encode("utf-8")).digest()
bucket = struct.unpack("<I", h[:4])[0] % self._dimensions
value = struct.unpack("<i", h[4:8])[0] / (2**31)
vector[bucket] += value
```

Using `struct.unpack` on raw bytes is faster than converting the hex digest and parsing integers from strings.

### L2 Normalization

After accumulation, the vector is L2-normalized to unit length. This ensures cosine similarity comparisons are valid — without normalization, vectors with more n-grams (longer texts) would have larger magnitudes and dominate similarity scores regardless of content.

## Configurable Parameters

- `dimensions` (default 64) — Vector length. Larger values reduce collision probability at the cost of memory.
- `ngram_size` (default 3) — Trigrams balance granularity with coverage. Larger n-grams are more specific; smaller ones produce more collisions.

## Limitations by Design

- The same input always produces the same output (good for tests).
- Different inputs may produce similar outputs by hash collision (acceptable for tests, unusable for production search).
- Semantically related texts ("dog" and "canine") produce completely unrelated vectors.

The class docstring is explicit: "The output is NOT semantically meaningful." This is a testing utility, not a search-quality tool.

## Known Gaps

No TODOs or FIXMEs. The `embed_batch()` method is a simple loop over `embed()` — no parallel execution. For a testing embedder this is fine; batch performance is irrelevant in test suites.