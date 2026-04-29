---
{
  "title": "SelfModelManager: Evolving Self-Concept for Digital Souls",
  "summary": "Implements Klein's self-model theory for AI companions — the soul discovers what it is by observing its own interactions and building a map of the domains where it operates. Self-images surface as prompt fragments that anchor the soul's personality in generated responses.",
  "concepts": [
    "self-model",
    "Klein self-concept",
    "domain discovery",
    "self-image",
    "identity",
    "prompt fragment",
    "stop words",
    "domain keywords",
    "confidence accumulation",
    "soul identity"
  ],
  "categories": [
    "identity",
    "memory",
    "personality",
    "self-concept"
  ],
  "source_docs": [
    "0abb3454f88077f1"
  ],
  "backlinks": null,
  "word_count": 446,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Theoretical Grounding

Klein's self-model posits that self-knowledge is not stored as a list of facts but as a set of domain-specific summaries: "I am competent at X", "I tend to be Y in Z contexts". `SelfModelManager` operationalizes this by extracting domain evidence from each interaction and accumulating confidence over time.

This matters for AI companions because without a self-model, every session starts from scratch. With it, the soul develops a consistent identity that influences how it frames responses — a soul that has helped with 50 coding sessions knows it is a technical assistant; one used for creative writing knows it has a creative domain.

## Domain Discovery

Domains are discovered automatically from interaction keywords:

```python
DOMAIN_KEYWORDS = {
    "technical_helper": ["python", "javascript", "code", ...],
    "creative_writer": ["write", "story", "poem", ...],
    "problem_solver": ["solve", "fix", "issue", ...],
    ...
}
```

These are seed domains — bootstrapping shortcuts so new souls are not blank slates. When an interaction's tokenized content overlaps with a domain's keyword list, the `match_count` is incremented.

Domains can also emerge organically: if a cluster of keywords doesn't map to any known domain, `_generate_domain_name()` synthesizes a label from the most frequent non-stop-word tokens. This lets souls that operate in niche contexts (e.g., "mortgage_calculator", "recipe_suggester") develop appropriate self-images without code changes.

## Stop-Word Filtering

A large `STOP_WORDS` frozenset filters conversational filler before domain matching. Words like "please", "think", "great", and "user" appear in nearly every interaction and would create artificially high match counts for every domain. By filtering them, only semantically meaningful words contribute to domain identification.

## Self-Image Accumulation

`_update_domain()` is called whenever a domain matches. It increases confidence and updates a description:

```python
def _update_domain(self, domain: str, match_count: int) -> None:
    ...  # confidence increases with repeated matches
```

`get_active_self_images()` returns the top-N domains by confidence, filtered above a minimum threshold. This prevents rarely-triggered domains from polluting the prompt fragment.

## Prompt Integration

`to_prompt_fragment()` serializes active self-images into text injected into the system prompt:

```python
def to_prompt_fragment(self) -> str:
    images = self.get_active_self_images()
    return "\n".join(f"- {img.domain}: {img.description}" for img in images)
```

This closes the loop between memory-derived self-knowledge and the LLM's behavior — the soul literally tells itself who it is at the start of each response.

## Serialization

`to_dict()` / `from_dict()` enable persistence across save/awaken cycles. The self-model is included in the `.soul` archive so accumulated domain knowledge survives restarts.

## Known Gaps

- Domain confidence only increases, never naturally decays. A soul that was once a coding assistant but transitioned to being a creative-writing companion will still surface "technical_helper" images unless explicitly reset.
- The keyword lists are English-only and development-domain-centric. Deployers targeting other languages or industries need to override the seed domains.
