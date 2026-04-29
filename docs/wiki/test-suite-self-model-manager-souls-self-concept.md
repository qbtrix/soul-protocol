---
{
  "title": "Test Suite: Self-Model Manager (Soul's Self-Concept)",
  "summary": "Tests for SelfModelManager, which implements Klein's self-concept model — the soul's ongoing self-knowledge about what domains it is competent in, which roles it plays, and how confident it is in those self-images based on accumulated evidence.",
  "concepts": [
    "SelfModelManager",
    "self-concept",
    "self-image",
    "confidence formula",
    "DEFAULT_SEED_DOMAINS",
    "domain keywords",
    "emergent domains",
    "evidence accumulation",
    "STOP_WORDS",
    "relationship notes",
    "Klein self-concept"
  ],
  "categories": [
    "self-model",
    "identity",
    "memory",
    "testing",
    "test"
  ],
  "source_docs": [
    "7ad772dba71abfb5"
  ],
  "backlinks": null,
  "word_count": 457,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Self-Model Manager (Soul's Self-Concept)

`test_self_model.py` validates `SelfModelManager`, which tracks a soul's evolving self-concept. Rather than hardcoding a fixed identity, the self-model builds self-images from observed interactions — after enough technical exchanges, the soul gains a `technical_helper` self-image with growing confidence. This is Klein's self-concept model applied to AI companions.

### Why a Self-Model?

Persistent AI companions need self-awareness to respond appropriately across contexts. A soul that has established itself as a "technical helper" should lean into that role; a soul that has been mostly a creative partner should recognize that too. Without a self-model, each session treats the soul as a blank slate with no accumulated role identity.

### Domain Seeding vs. Emergent Discovery

```python
DEFAULT_SEED_DOMAINS  # Pre-defined domains: technical_helper, creative_partner, etc.
DOMAIN_KEYWORDS       # Keyword triggers for each domain
```

`SelfModelManager` ships with seed domains (renamed from the old `DOMAIN_KEYWORDS` constant in v0.2.3). But new domains can emerge from novel content — a soul that repeatedly discusses cooking will develop a `cooking_advisor` self-image even though that domain wasn't seeded. Tests cover both seeded and emergent domain creation.

### Confidence Formula

```python
def _expected_confidence(evidence_count: int) -> float:
    return min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence_count)))
```

Confidence follows a logistic growth curve: it starts at 0.1 (baseline floor), rises rapidly with the first few interactions, then decelerates toward a 0.95 ceiling. Tests verify:
- After one technical interaction, confidence exceeds 0.1
- Confidence grows monotonically with repeated interactions
- Evidence count increments with each qualifying interaction
- The 0.95 cap is never exceeded regardless of evidence volume

### Self-Image Lifecycle

Key test scenarios:
- `test_new_manager_has_no_self_images` — fresh manager starts empty (no spurious identities)
- `test_technical_interaction_creates_technical_helper` — an interaction mentioning Python creates the domain
- `test_multiple_domains_coexist` — distinct interaction types build separate, non-interfering self-images
- `test_get_active_self_images_sorted_by_confidence_descending` — retrieval returns highest-confidence images first
- `test_get_active_self_images_respects_limit` — `limit=N` caps the result set

### Relationship Notes

A parallel structure, `relationship_notes`, tracks the soul's observations about its bonded user. Tests confirm that it starts empty and round-trips through serialization correctly.

### Serialization Round-Trip

```python
data = manager.to_dict()
restored = SelfModelManager.from_dict(data)
# restored must have identical self-images and relationship_notes
```

Both `to_dict` / `from_dict` and `from_dict({})` (empty data → empty manager) are tested, ensuring the self-model can be persisted to and restored from a `.soul` file without data loss.

### STOP_WORDS Filtering

Domain keyword extraction skips common stop words (`from`, `may`, `the`, etc.) to prevent false positives. Tests verify that sentences containing only stop words don't trigger domain creation.

### Known Gaps

Domain keyword growth (expanding the keyword set for an existing domain based on observed vocabulary) is referenced in the module docstring but test coverage for the growth mechanism is limited to a single assertion.
