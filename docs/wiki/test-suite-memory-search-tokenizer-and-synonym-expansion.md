---
{
  "title": "Test Suite: Memory Search Tokenizer and Synonym Expansion",
  "summary": "Tests for two search quality improvements (issues #10 and #11): a tokenizer that splits on code-style separators like slashes and underscores, and a synonym expansion layer that maps programming terms to related aliases so queries for 'database' match memories containing 'postgresql'.",
  "concepts": [
    "tokenizer",
    "synonym expansion",
    "relevance_score",
    "BM25",
    "memory search",
    "snake_case",
    "file paths",
    "token overlap",
    "search quality",
    "programming synonyms",
    "_SYNONYM_MAP"
  ],
  "categories": [
    "search",
    "memory",
    "testing",
    "tokenization",
    "test"
  ],
  "source_docs": [
    "6026d67a167fbc33"
  ],
  "backlinks": null,
  "word_count": 433,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Memory Search Tokenizer and Synonym Expansion

`test_search_improvements.py` validates two targeted fixes to soul-protocol's memory search pipeline. Before these fixes, queries containing code identifiers (`user_session_token`) or technical synonyms (`database` vs `postgresql`) frequently returned no results because the tokenizer treated the entire identifier as a single token and the index had no synonym awareness.

### Issue #11: Tokenizer Must Split on Code Separators

The original `tokenize()` function split only on whitespace. This caused `app/routes/handler` to be indexed as one token, making individual path components unsearchable.

The fix adds splitting on `/`, `_`, `-`, and `.` in addition to whitespace:

```python
tokens = tokenize("user_session_token")
assert "user" in tokens
assert "session" in tokens
assert "token" in tokens
```

`TestTokenizerSplitsOnSeparators` covers:
- Forward slashes (file paths)
- Underscores (snake_case identifiers)
- Hyphens (kebab-case)
- Dots (file extensions, module paths)
- Mixed separators in a single string
- Consecutive separators (no empty tokens)
- Real-world path like `src/core/memory_manager.py`

The short-token filter (tokens under 2 characters are dropped) is also verified so that separator characters themselves don't pollute the token set.

### Issue #10: Synonym Expansion

`_expand_synonyms()` uses `_SYNONYM_MAP` to add related terms to a token set before scoring:

```python
# "database" → also indexes as {"db", "sql", "postgresql", "mysql", ...}
# "deploy" → also indexes as {"deployment", "release", "ship", "cd"}
```

`TestSynonymExpansion` verifies:
- Common programming synonyms (`database` ↔ `db`, `sql`)
- Reverse synonym lookup (`postgresql` → `database`)
- Terms without synonyms pass through unchanged
- Multiple tokens where some have synonyms and some don't
- The synonym map is symmetric (if A → B then B → A)

Covered synonym groups include: `database`, `python`, `deploy`, `auth`, `docker/container`, `test/pytest`.

### Integration: relevance_score

`TestRelevanceScoreWithImprovements` tests the end-to-end search function with both fixes active:

- A query for a file path (`app/routes/handler`) matches memory content containing `routes`
- A query for `database` matches content containing `postgresql`
- A query for `deploy` matches content about `deployment`
- Synonym expansion never inflates the score above 1.0 (no score overflow)
- Empty queries still return 0.0
- Exact matches still return 1.0 (no regression)

### Why These Fixes Matter

Without them, a soul that learned "use postgresql for the main database" would not surface that memory when a user later asks about "database setup" — the token mismatch silently hides relevant context. These two fixes close the most common failure modes for developer-oriented use cases where identifiers and technical jargon are the norm.

### Known Gaps

The synonym map is a hand-curated static dictionary. Domain-specific synonyms (e.g., industry jargon, product names) are not auto-discovered. Expanding the map requires a code change.
