---
{
  "title": "EmbeddingProvider Protocol Re-export (Runtime Shim)",
  "summary": "This file is a one-line shim that re-exports `EmbeddingProvider` from its canonical location in `soul_protocol.spec.embeddings.protocol` into the runtime embeddings namespace. It exists to provide a stable import path for runtime code while keeping the authoritative protocol definition in the spec layer.",
  "concepts": [
    "EmbeddingProvider",
    "protocol",
    "spec layer",
    "runtime layer",
    "re-export",
    "structural typing",
    "duck typing",
    "two-layer architecture"
  ],
  "categories": [
    "embeddings",
    "architecture",
    "package structure"
  ],
  "source_docs": [
    "acf13b56aebdc2bb"
  ],
  "backlinks": null,
  "word_count": 265,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol follows a two-layer architecture: the `spec` layer defines protocols, models, and contracts; the `runtime` layer implements them. The `EmbeddingProvider` protocol — the interface that all embedding backends must satisfy — belongs in the spec layer.

However, runtime code working with embeddings imports from `soul_protocol.runtime.embeddings`. Requiring runtime consumers to reach into the spec layer directly would create coupling between two layers that should remain independent.

This shim bridges that gap:

```python
from soul_protocol.spec.embeddings.protocol import EmbeddingProvider

__all__ = ["EmbeddingProvider"]
```

## Why This Pattern?

If the spec layer ever reorganizes (e.g., moving `EmbeddingProvider` to `spec.core`), only this shim needs to change. All runtime consumers continue importing from `soul_protocol.runtime.embeddings.protocol` without modification.

Conversely, if the runtime embeddings module ever gains its own additional protocol types, they can be added here alongside the spec re-export — a consistent single import point.

## History

The module comment records two refactor events:
- **v0.4.0**: The canonical definition moved from an earlier location to `spec/embeddings/protocol.py`.
- **Runtime restructure**: The import path changed from `core` to `spec`, reflecting a package reorganization.

Both changes were absorbed here, keeping all downstream runtime imports stable.

## What is EmbeddingProvider?

`EmbeddingProvider` is a structural protocol (duck-typed interface) that all embedding backends must satisfy. Implementations must provide:
- `dimensions: int` — the vector length
- `embed(text: str) -> list[float]` — single text embedding
- `embed_batch(texts: list[str]) -> list[list[float]]` — batch embedding

Any class implementing these methods satisfies the protocol without explicit inheritance.

## Known Gaps

No TODOs or FIXMEs. This file is intentionally minimal — its only job is to provide a stable import target.