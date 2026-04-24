---
{
  "title": "Identity Subpackage: DID Generation Interface",
  "summary": "The `identity/__init__.py` init exposes `generate_did` as the single public entry point for the identity subsystem, making Decentralized Identifier (DID) creation available via `from soul_protocol.runtime.identity import generate_did` without exposing the underlying DID implementation details.",
  "concepts": [
    "generate_did",
    "DID",
    "Decentralized Identifier",
    "soul identity",
    "did:soul",
    "identity subpackage",
    "self-sovereign identity",
    "package init"
  ],
  "categories": [
    "identity",
    "DID",
    "package-structure",
    "architecture"
  ],
  "source_docs": [
    "7a7b12057cd91562"
  ],
  "backlinks": null,
  "word_count": 274,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Every soul in Soul Protocol has a Decentralized Identifier (DID) — a globally unique, self-sovereign identifier that does not depend on a central authority. The `identity/` subpackage houses the logic for generating and managing these identifiers, and `__init__.py` presents its public surface.

```python
from soul_protocol.runtime.identity.did import generate_did
__all__ = ["generate_did"]
```

## Why a Subpackage for Identity

Identity in Soul Protocol is more than just generating a random ID. The DID standard (`did:soul:<identifier>`) carries semantic meaning: it signals that the identifier is owned by the soul itself, portable across platforms, and verifiable. The subpackage structure anticipates growth:

- **Today:** `did.py` — `generate_did()` creates `did:soul:<hash>` identifiers
- **Future:** `resolver.py` — resolve a DID to a document; `verifier.py` — verify ownership proofs; `migrate.py` — transfer DID ownership across platforms

By routing all external imports through `__init__.py`, the internal module layout can expand without breaking callers.

## Data Flow

```
generate_did(name, seed)
  → soul_protocol.runtime.identity.did
  → returns "did:soul:<content-hash>"
```

The DID is assigned once at soul creation (`born` timestamp, soul name, and optional seed as inputs) and never changes — even as the soul evolves, migrates platforms, or changes its name. This immutability is intentional: the DID is the soul's permanent anchor in the decentralized identity space.

## Import Path History

Like other subpackages in the runtime, the identity module was updated from `soul_protocol.core.identity` to `soul_protocol.runtime.identity` during the runtime restructure. The init absorbed this change silently.

## Known Gaps

No DID resolver or verifier is implemented yet. `generate_did` produces identifiers, but there is currently no mechanism to resolve a `did:soul:` identifier to a document or verify that a claimed DID belongs to a given soul file.