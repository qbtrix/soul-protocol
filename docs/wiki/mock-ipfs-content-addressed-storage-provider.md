---
{
  "title": "Mock IPFS Content-Addressed Storage Provider",
  "summary": "`MockIPFSProvider` simulates IPFS's content-addressed storage model by generating deterministic CID-like references from the SHA-256 hash of the archived data and storing it in memory. It faithfully reproduces the key property of IPFS — the same content always produces the same address — without requiring a running IPFS node.",
  "concepts": [
    "MockIPFSProvider",
    "IPFS",
    "CID",
    "content-addressed storage",
    "deterministic hash",
    "idempotent archive",
    "EternalStorageProvider",
    "bafybeig",
    "pinning",
    "deduplication"
  ],
  "categories": [
    "eternal-storage",
    "providers",
    "testing",
    "ipfs"
  ],
  "source_docs": [
    "9fa38c90d930f958"
  ],
  "backlinks": null,
  "word_count": 343,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

IPFS (InterPlanetary File System) is a content-addressed distributed storage network. Its defining characteristic: the address of any file is derived from the file's content hash (a CID — Content Identifier). Store the same bytes twice and you get the same address both times.

`MockIPFSProvider` preserves this semantic while eliminating the dependency on a running IPFS daemon or Pinata/Infura gateway. This makes soul archive tests hermetic and instant.

## Content-Addressed Semantics

### Deterministic CID Generation

```python
def _generate_cid(self, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"bafybeig{digest[:48]}"
```

Real IPFS CIDv1 addresses start with `bafy` for SHA-2-256 encoded as base32. The mock mimics this with `bafybeig` prefix followed by 48 hex chars from the actual SHA-256 of the data. The result looks plausible to any code that checks CID format, and — critically — the same content always maps to the same CID. This is the foundational IPFS property the mock must preserve.

### Idempotent Archive

Because the CID is derived purely from content, calling `archive()` twice with identical `soul_data` stores the same key in `_store` and returns the same `ArchiveResult`. This matches IPFS's deduplication behavior, where uploading the same content to the network is a no-op that returns the existing CID.

### Permanence Flag

```python
permanent=False  # IPFS requires pinning for permanence
```

Unlike Arweave, IPFS content is only retained as long as at least one node pins it. Without a pinning service, garbage collection will eventually remove it. The mock correctly signals `permanent=False` to distinguish IPFS from Arweave in the tier hierarchy.

## Data Flow

```
archive(soul_data, soul_id)
  → _generate_cid(soul_data) → "bafybeig<48-char hex>"
  → _store[cid] = soul_data
  → ArchiveResult(tier="ipfs", reference=cid, url="https://ipfs.io/ipfs/<cid>", permanent=False)

retrieve(reference)  [reference IS the CID]
  → _store[cid] → bytes or KeyError

verify(reference)
  → cid in _store
```

## Known Gaps

- No simulation of network propagation — real IPFS requires peers to replicate the content before it becomes reliably retrievable. The mock returns instantly.
- Pinning is not modeled. There is no concept of a pinned vs. unpinned CID in the mock store, so `permanent=False` is advisory only.