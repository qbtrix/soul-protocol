---
{
  "title": "DID Generation for Digital Souls",
  "summary": "Generates decentralized identifiers (DIDs) for soul instances using the `did:soul:` method. Each DID is deterministically random — human-readable yet collision-resistant — by combining the soul's name with a UUID4-seeded SHA-256 hash.",
  "concepts": [
    "decentralized identifier",
    "DID",
    "did:soul",
    "UUID4",
    "SHA-256",
    "soul identity",
    "name normalization",
    "collision resistance",
    "digital soul protocol"
  ],
  "categories": [
    "identity",
    "cryptography",
    "soul-protocol-core"
  ],
  "source_docs": [
    "04573694a30b8ff2"
  ],
  "backlinks": null,
  "word_count": 377,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Every soul in the Digital Soul Protocol needs a stable, globally unique identity that is also recognizable to humans. The `did.py` module provides exactly one exported function — `generate_did()` — which produces identifiers in the `did:soul:` namespace.

## Why DIDs?

Decentralized identifiers (DIDs) let souls carry their identity across platforms without depending on a central registry. Unlike database auto-increment IDs or UUIDs alone, a DID encodes the soul's name in a readable prefix, making logs and exports human-scannable while still being unique across the network.

## How the Identifier Is Built

```python
def generate_did(name: str) -> str:
    entropy = f"{name}{uuid.uuid4()}"
    digest = hashlib.sha256(entropy.encode()).hexdigest()
    suffix = digest[:6]
    clean_name = name.strip().lower().replace(" ", "-")
    return f"did:soul:{clean_name}-{suffix}"
```

The algorithm has three steps:

1. **Entropy injection** — a fresh `uuid4()` is concatenated to the name before hashing. This prevents two souls with the same name from generating the same DID even if called at the same millisecond.
2. **SHA-256 digest** — the combined string is hashed and the first 6 hex characters are taken as the suffix. Six hex characters give ~16 million distinct values per name, which is more than enough for a personal-scale protocol.
3. **Name normalization** — spaces become hyphens, the name is lowercased, and leading/trailing whitespace is stripped so the prefix is always a valid URL-safe segment.

**Example output:** `did:soul:aria-7x8k2m`

## Design Tradeoffs

- **Non-deterministic by design.** Calling `generate_did("Aria")` twice produces different DIDs. This is intentional: the protocol treats each `Soul.birth()` call as creating a genuinely new entity. If determinism were needed (e.g. re-importing the same soul), the caller would need to pass a fixed seed, which is not currently supported.
- **Short suffix.** Six hex characters keep the DID compact for display. Collision probability over realistic usage (thousands of souls per deployment) is negligible.
- **No verification.** The DID is not registered with any resolver at generation time. Resolver integration (e.g. DID document publication to Arweave) is handled at a higher layer.

## Known Gaps

- No option to supply a deterministic seed for reproducible DIDs — callers that need stable IDs across re-imports must store and reuse the generated DID themselves.
- No DID document creation or resolver registration at birth — eternal storage integration is a separate concern handled outside this module.