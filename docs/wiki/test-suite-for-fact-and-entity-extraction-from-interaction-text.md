---
{
  "title": "Test Suite for Fact and Entity Extraction from Interaction Text",
  "summary": "Validates the pattern-based extraction pipeline that parses user messages for facts (name, preferences, identity, tools, projects) and entities (tech terms, proper nouns with inferred relations). Tests cover each extraction pattern, punctuation stripping, stopword exclusion, and deduplication of repeated facts.",
  "concepts": [
    "fact extraction",
    "entity extraction",
    "regex patterns",
    "proper nouns",
    "tech terms",
    "MemoryManager",
    "trailing punctuation",
    "deduplication",
    "semantic facts",
    "relation inference",
    "stopword exclusion",
    "extraction pipeline"
  ],
  "categories": [
    "testing",
    "memory",
    "extraction",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "d78090b11557f83d"
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

## Overview

`test_extraction.py` verifies the extraction layer that automatically converts raw conversational text into structured semantic facts and named entities. Rather than requiring the soul to be told facts explicitly (via `soul_remember`), extraction passively mines user input for memorable information — a key part of what makes souls feel attentive.

## Fact Extraction Patterns

Each test exercises a specific linguistic pattern that the extractor recognizes:

| Test | Pattern | Example |
|---|---|---|
| `test_extract_name` | "my name is X" | "my name is Alex" → fact: user name is Alex |
| `test_extract_preference` | "I prefer/hate X" | "I hate meetings" → fact: dislikes meetings |
| `test_extract_technical_tool` | "I use/work with X" | "I use Docker" → fact: uses Docker |
| `test_extract_identity_facts` | "I work at/live in/am from X" | "I work at Stripe" → fact: works at Stripe |
| `test_extract_building_pattern` | "I'm building X" | "I'm building a CLI tool" → fact: building CLI tool |
| `test_extract_favorite_pattern` | "my favorite X is Y" | "my favorite language is Python" → fact: favorite language is Python |

These patterns were chosen because they are the most common ways users naturally disclose personal information in conversation. The extraction operates without LLM inference — pure regex — making it fast and deterministic.

## Negative Cases

```python
def test_no_facts_from_empty_input():
    # Empty string → zero facts extracted (no crash, no phantom facts)

def test_strips_trailing_punctuation():
    # "my name is Alice." → fact value is "Alice", not "Alice."
    # Trailing punctuation must be stripped from captured groups
```

The trailing punctuation test matters for deduplication: "Alice" and "Alice." would be treated as different facts by the Jaccard-based dedup system, producing false duplicates. Stripping during extraction prevents this.

## Entity Extraction

Beyond structured facts, the extractor identifies named entities and tech terms from free text:

```python
def test_extract_entities_from_text():
    # Extracts known tech terms (Python, Docker, etc.) from interaction text

def test_extract_entities_proper_nouns():
    # Capitalised words NOT at sentence start are detected as proper nouns

def test_extract_entities_with_relation():
    # "I use Python" → entity Python with relation "uses"

def test_extract_entities_building_relation():
    # "I'm building MyApp" → entity MyApp with type "project" and relation "builds"

def test_extract_entities_no_stop_words():
    # "I", "the", "and", etc. must not appear as extracted entities
```

The sentence-start exception for capitalization prevents false positives: "The user" should not extract "The" as a proper noun just because sentences start with capital letters.

## Deduplication of Extracted Facts

```python
async def test_no_duplicate_facts():
    # Adding the same extracted fact twice should not create two entries
    # The extraction output feeds the dedup layer; this test verifies the integration
```

This integration test confirms that the extraction → dedup pipeline is correctly wired. Without it, a user who says "my name is Alex" twice in a session would end up with two identical name facts.

## MemoryManager Fixture

The `manager()` fixture creates a fresh `MemoryManager` with default settings for each test. Using a fresh instance prevents test ordering dependencies — each test starts with a clean memory store.

## Known Gaps

No TODOs flagged. The extractor uses regex patterns, so it cannot handle paraphrases (e.g., "call me Alex" instead of "my name is Alex"). LLM-based extraction for non-standard phrasing is not tested here because it lives in a different module.