---
{
  "title": "BM25 and Token-Overlap Memory Search Engine",
  "summary": "Implements the core text-matching primitives used by all three memory stores: a tokenizer that handles natural language and code identifiers, a BM25 index with IDF weighting, and a lightweight token-overlap relevance scorer kept as a fast fallback. Synonym expansion improves recall for common programming and technical terms.",
  "concepts": [
    "BM25",
    "token-overlap",
    "relevance scoring",
    "tokenizer",
    "synonym expansion",
    "IDF weighting",
    "memory search",
    "text retrieval",
    "term frequency",
    "document length normalization"
  ],
  "categories": [
    "memory",
    "search",
    "text-retrieval",
    "indexing"
  ],
  "source_docs": [
    "e3a941bc62847b4e"
  ],
  "backlinks": null,
  "word_count": 412,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why Not Just Use `in` or `str.find`?

Early soul-protocol used substring matching for memory search. The problems: it can't rank results (all matches are equal), it misses plural/variant forms, and it breaks on identifiers like `user_id` (searching "user" would miss `user_id`). `search.py` replaces all of that with a principled text-retrieval stack.

## Tokenizer Design

`tokenize()` splits on whitespace *and* common identifier/path separators (`, /, _, -, .`):

```python
_SPLIT_RE = re.compile(r"[\s/_.\\-]+")
_ALPHA_RE = re.compile(r"[^a-z]+")

def tokenize(text: str, *, min_length: int = 3) -> set[str]:
    tokens = _SPLIT_RE.split(text.lower())
    return {_ALPHA_RE.sub("", t) for t in tokens if len(t) >= min_length}
```

Splitting on `.` means `os.environ` becomes `{"os", "environ"}` — both components are independently searchable. Stripping non-alpha characters strips digits and symbols from token interiors, preventing code snippets like `os.environ.get('KEY')` from creating junk tokens like `getkey`.

## Synonym Expansion

`_expand_synonyms()` adds related terms so a query for "database" also matches memories mentioning "postgresql" or "sqlite":

```python
_SYNONYM_GROUPS = [
    ("database", "sql", "postgresql", "postgres", ...) ,
    ("javascript", "typescript"),
    ("auth", "authentication", "login"),
    ...
]
```

This is deliberately curated and small — generic synonyms would pollute results. The list covers the most common programming domain mismatches (issue #10).

## BM25 Index

`BM25Index` provides term-frequency saturation (k1=1.2) and document-length normalization (b=0.75):

```python
class BM25Index:
    def score(self, query: str, doc_id: str) -> float:
        ...
```

IDF weighting means rare terms carry more signal than common ones, avoiding the "the/and/is" noise problem. The `k1` saturation parameter prevents a document from gaming the score simply by repeating a term many times.

The index is maintained incrementally — `add()` and `remove()` allow `BM25SearchStrategy` in `strategy.py` to keep the corpus synchronized as memories are added or deleted without full rebuilds.

## Token-Overlap Fallback

`relevance_score()` is a simpler O(n) scorer kept alongside BM25:

```python
def relevance_score(query: str, content: str) -> float:
    q_tokens = _expand_synonyms(tokenize(query))
    c_tokens = tokenize(content)
    overlap = q_tokens & c_tokens
    return len(overlap) / len(q_tokens) if q_tokens else 0.0
```

It returns 0.0–1.0 based on what fraction of query tokens appear in the content. This is used by `ProceduralStore` and `SemanticStore` directly (they manage their own scoring rather than delegating to the strategy layer).

## Known Gaps

- The BM25 IDF calculation uses corpus size at scoring time, so scores are not stable as the corpus grows — a term's IDF drops as more documents are added, making historical scores incomparable.
- Synonym groups cover English programming terms only; non-English deployments or domain-specific vocabularies (medical, legal) would need custom expansion tables.
