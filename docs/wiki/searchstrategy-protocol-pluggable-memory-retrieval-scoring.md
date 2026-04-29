---
{
  "title": "SearchStrategy Protocol: Pluggable Memory Retrieval Scoring",
  "summary": "Defines a Protocol interface for memory retrieval scoring, enabling consumers to replace the default BM25 scorer with embeddings, vector databases, or any custom implementation. Ships with two built-in strategies: a zero-dependency token-overlap fallback and a BM25-backed default.",
  "concepts": [
    "SearchStrategy",
    "protocol interface",
    "BM25",
    "token-overlap",
    "pluggable retrieval",
    "RecallEngine",
    "embedding search",
    "IDF weighting",
    "TF saturation",
    "strategy pattern"
  ],
  "categories": [
    "memory",
    "search",
    "architecture",
    "retrieval"
  ],
  "source_docs": [
    "87a9dd4334613206"
  ],
  "backlinks": null,
  "word_count": 542,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Design Motivation

Different Soul Protocol deployments have radically different resource constraints. An embedded IoT assistant cannot afford embedding model calls; a cloud-based companion can afford semantic vector search. The `SearchStrategy` protocol decouples the retrieval algorithm from the recall pipeline so each deployment picks the right tradeoff.

This mirrors the `CognitiveEngine` pattern elsewhere in Soul Protocol: instead of hardcoding a specific algorithm, the system defines a one-method protocol that any class can satisfy.

## The Protocol Interface

```python
@runtime_checkable
class SearchStrategy(Protocol):
    def score(self, query: str, content: str) -> float:
        ...
```

`@runtime_checkable` means `isinstance(obj, SearchStrategy)` works at runtime — useful for defensive checks in `RecallEngine` without importing a concrete class. The single `score()` method returns 0.0–1.0; the protocol imposes no requirements on initialization, making it trivially implementable:

```python
class MyEmbeddingSearch:
    def score(self, query: str, content: str) -> float:
        return cosine_similarity(embed(query), embed(content))
```

## TokenOverlapStrategy: Zero-Dependency Fallback

Wraps `relevance_score()` from `search.py` directly. Included for backwards compatibility — deployments that instantiated `RecallEngine` without a strategy argument before v0.2.2 continue working unchanged:

```python
class TokenOverlapStrategy:
    def score(self, query: str, content: str) -> float:
        return relevance_score(query, content)
```

## BM25SearchStrategy: Default Since Phase-1 Ablation

The production default. Maintains an internal `BM25Index` that stays synchronized as memories are added and removed:

```python
class BM25SearchStrategy:
    def __init__(self) -> None:
        self._index = BM25Index()
    
    def add(self, content: str) -> None:
        self._index.add(content)
    
    def score(self, query: str, content: str) -> float:
        return self._index.score(query, content)
```

BM25 outperforms pure token-overlap because it applies IDF weighting (rare terms matter more than common ones) and TF saturation (repeating a term 10 times is not 10x better than saying it once). The phase-1 ablation study confirmed measurable recall quality improvement switching from `TokenOverlapStrategy` to `BM25SearchStrategy` as the default.

## Index Synchronization

`BM25SearchStrategy.add()` and `remove()` keep the BM25 corpus in sync with the memory store. This is critical: if a deleted memory's document remains in the BM25 index, its IDF contribution continues to bias scores for other documents, degrading retrieval quality over time.

## Known Gaps

- `BM25SearchStrategy` maintains an independent corpus. If multiple strategy instances are created for the same soul (e.g., due to a coding error), they diverge. The strategy should be treated as a singleton per soul.
- There is no serialization for `BM25SearchStrategy` — the index is rebuilt from scratch each time the soul awakens. For large memory stores this adds startup latency.

## Custom Strategy Implementation

Any class with a `score(query, content) -> float` method satisfies the protocol. A vector embedding strategy looks like:

```python
class OpenAIEmbeddingSearch:
    def __init__(self, client):
        self._client = client
        self._cache = {}

    def score(self, query: str, content: str) -> float:
        q_vec = self._embed(query)
        c_vec = self._embed(content)
        return cosine_similarity(q_vec, c_vec)
```

Because `SearchStrategy` is a structural protocol (not a base class), there is no import coupling — the custom strategy can live in the consumer's codebase and be injected at `Soul.birth()` or `RecallEngine` construction time without depending on any soul-protocol internals beyond the float return type.

## When to Switch Strategies

- **Development / testing**: `TokenOverlapStrategy` — zero dependencies, deterministic, no network calls.
- **Production without GPU**: `BM25SearchStrategy` — measurably better recall quality at zero inference cost.
- **Production with embedding model**: Custom `EmbeddingStrategy` — semantic search, handles synonyms and paraphrase natively but adds latency and cost per lookup.
