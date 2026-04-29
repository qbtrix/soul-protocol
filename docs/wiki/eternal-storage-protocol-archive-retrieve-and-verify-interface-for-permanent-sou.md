---
{
  "title": "Eternal Storage Protocol — Archive, Retrieve, and Verify Interface for Permanent Soul Backends",
  "summary": "This module defines the canonical protocol and result models for Soul Protocol's eternal (permanent) storage tier. `EternalStorageProvider` is a runtime-checkable async `Protocol` that any backend (IPFS, Arweave, local) must satisfy, while `ArchiveResult` and `RecoverySource` capture what an archival operation produces and how a soul can later be restored.",
  "concepts": [
    "EternalStorageProvider",
    "ArchiveResult",
    "RecoverySource",
    "eternal storage",
    "IPFS",
    "Arweave",
    "archive",
    "retrieve",
    "verify",
    "soul recovery",
    "content-addressed storage",
    "permanent storage",
    "async protocol"
  ],
  "categories": [
    "eternal storage",
    "spec layer",
    "soul archival",
    "protocol interfaces"
  ],
  "source_docs": [
    "88099d5d48dc8bd2"
  ],
  "backlinks": null,
  "word_count": 514,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Eternal storage is what makes Soul Protocol's identity persistence guarantees real. A soul stored only on a single platform is one outage away from disappearing. The eternal tier writes a full soul snapshot to a content-addressed, append-only network so it can be recovered from any compatible runtime, even if the original host is gone.

This module defines the interface contract, not the implementation. Real backends (IPFS via `py-ipfs-http-client`, Arweave via `arweave-python-client`, or a local file store for tests) live in the engine layer.

## `ArchiveResult`

```python
class ArchiveResult(BaseModel):
    tier: str          # "ipfs", "arweave", "blockchain"
    reference: str     # CID, txId, etc.
    url: str = ""      # Human-readable URL
    cost: str = "$0.00"
    permanent: bool = False
    archived_at: datetime
    metadata: dict[str, Any]
```

`permanent: bool` distinguishes truly immutable storage (Arweave, blockchain) from pinned-but-mutable storage (IPFS pinning service). Callers that need sovereignty guarantees can check this flag and refuse to treat the archive as a recovery source until `permanent=True`.

The `cost` field is a string (not a float) to avoid currency ambiguity — some backends report in USD, others in AR tokens. The runtime formats it for display but never does arithmetic on it.

## `RecoverySource`

```python
class RecoverySource(BaseModel):
    tier: str
    reference: str
    available: bool = True
    last_verified: datetime
```

A soul's manifest can hold multiple `RecoverySource` entries — one per backend used. The `available` flag is toggled by the `verify()` operation. If IPFS goes offline but Arweave is available, recovery can fall back to the next source. This is why `last_verified` exists: recovery code sorts sources by recency of verification before attempting retrieval.

## `EternalStorageProvider` Protocol

```python
@runtime_checkable
class EternalStorageProvider(Protocol):
    @property
    def tier_name(self) -> str: ...

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs) -> ArchiveResult: ...
    async def retrieve(self, reference: str, **kwargs) -> bytes: ...
    async def verify(self, reference: str) -> bool: ...
```

### `archive(soul_data, soul_id)`
Accepts the raw bytes of a `.soul` zip archive and the soul's ID. Returns an `ArchiveResult`. The `**kwargs` escape hatch lets backends accept tier-specific options (number of Arweave replications, IPFS pinning provider, etc.) without breaking the interface.

### `retrieve(reference)`
Fetches and returns the raw bytes of a previously archived soul. The `reference` is whatever the `ArchiveResult` recorded — a CID for IPFS, a transaction ID for Arweave. Callers pass the reference to `unpack_soul()` to reconstruct the soul's identity and memories.

### `verify(reference) -> bool`
Checks whether the archived data still exists and is accessible without fetching the full payload. Used by background health checks and by the recovery planner when ranking `RecoverySource` entries. An IPFS backend might call `ipfs cat --length 1` to verify presence cheaply.

### `tier_name` property
The human-readable name of the storage tier (`"ipfs"`, `"arweave"`, `"local"`). Used in `ArchiveResult.tier` and logged for observability.

## Data Flow

```
.soul bytes
  └─ EternalStorageProvider.archive() -> ArchiveResult
       └─ reference saved as RecoverySource in manifest
            └─ EternalStorageProvider.verify(reference) -> bool  [periodic]
                 └─ EternalStorageProvider.retrieve(reference) -> bytes  [on restore]
                      └─ unpack_soul(bytes) -> (Identity, layers)
```

## Known Gaps

None explicitly flagged. The `**kwargs` on `archive` and `retrieve` is intentionally permissive — specific backends document their accepted kwargs in their own modules.