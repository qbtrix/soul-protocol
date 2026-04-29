---
{
  "title": "TF-IDF Embedder: Vocabulary-Fitted Semantic Embeddings",
  "summary": "The `TFIDFEmbedder` builds corpus-fitted TF-IDF vectors using only Python's standard library — no external dependencies. It produces semantically meaningful similarity (unlike `HashEmbedder`) but requires a `fit()` call on a corpus before embedding, making it useful for lightweight production use cases where a known document set exists.",
  "concepts": [
    "TFIDFEmbedder",
    "TF-IDF",
    "vocabulary fitting",
    "IDF smoothing",
    "tokenization",
    "L2 normalization",
    "zero vector",
    "fit()",
    "stdlib embedder",
    "term frequency"
  ],
  "categories": [
    "embeddings",
    "memory search",
    "NLP"
  ],
  "source_docs": [
    "e7e79bb1834dfac8"
  ],
  "backlinks": null,
  "word_count": 480,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`TFIDFEmbedder` fills the space between the fully non-semantic `HashEmbedder` (testing only) and the heavy optional providers (sentence-transformers, OpenAI, Ollama). It uses term frequency-inverse document frequency weighting to produce vectors where texts with similar word distributions have high cosine similarity — without any external dependencies or model downloads.

## How TF-IDF Embedding Works

### Step 1: Tokenization

```python
def _tokenize_text(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2]
```

Lowercasing and filtering to alphanumeric tokens of 2+ characters removes stop words, punctuation, and single-character noise.

### Step 2: Fit — Build Vocabulary and IDF

```python
def fit(self, texts: list[str]) -> None:
    ...
    # Select top `dimensions` terms by document frequency
    sorted_terms = sorted(doc_freq.items(), key=lambda x: (-x[1], x[0]))
    top_terms = sorted_terms[:self._dimensions]
    # IDF with smoothing
    self._idf = {term: math.log((1 + N) / (1 + df)) + 1.0 for term, df in ...}
```

The IDF smoothing formula `log((1 + N) / (1 + df)) + 1.0` prevents division-by-zero for terms appearing in every document (where `df == N`) while still downweighting ubiquitous terms. The `+1.0` offset ensures IDF is never negative.

Vocabulary is capped at `dimensions` (default 128) by keeping only the highest document-frequency terms — common terms that appear across many documents are most useful for discrimination.

### Step 3: Embed — TF-IDF Vector Construction

```python
# TF normalized by max TF in document (avoids length bias)
tf[token] = tf[token] / max_tf
# Multiply by IDF for final weight
vector[idx] = freq * idf
```

TF is normalized by the document's maximum term frequency rather than total length, which reduces the bias toward longer documents. Out-of-vocabulary terms (not in the fitted vocabulary) are silently ignored.

### Step 4: L2 Normalization

The final vector is L2-normalized for consistent cosine similarity scoring.

## Guard: embed() Before fit()

If `embed()` is called before `fit()`, the embedder returns a zero vector and emits a `warnings.warn()` rather than raising an exception:

```python
warnings.warn(
    "TFIDFEmbedder.embed() called before fit() — returning zero vector",
    stacklevel=2,
)
```

A zero vector silently degrades search quality rather than crashing the application. The warning gives developers visibility into the misconfiguration. The `stacklevel=2` points the warning at the caller, not inside the embedder.

## Trade-offs vs Other Providers

| Property | TFIDFEmbedder | HashEmbedder | SentenceTransformer |
|----------|--------------|-------------|--------------------|
| Semantic | Partial | None | Full |
| Dependencies | None | None | Heavy |
| Requires fit | Yes | No | No |
| Quality | Low-medium | N/A | High |

## Known Gaps

- Vocabulary is static after `fit()`. If new terms appear in the soul's memory that weren't in the original corpus, they are out-of-vocabulary and silently ignored. There is no incremental `partial_fit()` mechanism.
- The zero-vector fallback for pre-fit calls could mask bugs in callers that forget to fit — a stricter option would be to raise `RuntimeError`.