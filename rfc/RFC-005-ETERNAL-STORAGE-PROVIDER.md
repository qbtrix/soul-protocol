<!-- RFC-005-ETERNAL-STORAGE-PROVIDER.md — Defines the EternalStorageProvider protocol, -->
<!-- storage tiers, archive/recover operations, content addressing, and production roadmap. -->

# RFC-005: Eternal Storage Provider

**Status:** Draft -- Open for feedback
**Author:** Soul Protocol Community
**Date:** 2026-03-08
**Amended:** 2026-08-15 (#293) — Added `content_addressed` property and
`compute_reference()` method to prevent substitution attacks on `recover()`.

## Summary

Digital souls should outlive the platforms that host them. The `EternalStorageProvider`
protocol defines a pluggable interface for archiving soul data to decentralized and
durable storage backends -- IPFS, Arweave, blockchain anchoring, or local filesystem.
The protocol specifies three async operations (archive, retrieve, verify) and two data
models (ArchiveResult, RecoverySource). Current implementations are mock providers for
development. Production integrations with real decentralized storage are planned.

## Problem Statement

AI companion data is fragile. A platform shutdown, a database migration, or a billing
dispute can erase years of accumulated memory, personality evolution, and emotional
bonds. Users have no recourse because:

1. Data lives on the platform's servers, not in the user's control
2. There is no standard archive format that survives platform death
3. No verification mechanism confirms that archived data is still retrievable
4. Recovery from backups requires platform-specific tooling

Eternal storage means the soul persists even if every platform that ever hosted it
goes offline.

## Proposed Solution

### EternalStorageProvider Protocol

The spec defines the interface in `spec/eternal/protocol.py`:

```python
@runtime_checkable
class EternalStorageProvider(Protocol):
    """Interface for any eternal storage backend."""

    @property
    def tier_name(self) -> str:
        """Name of this storage tier (e.g., 'ipfs', 'arweave')."""
        ...

    @property
    def content_addressed(self) -> bool:
        """Whether this tier uses content-addressing (e.g. IPFS CID).

        When True, recover() verifies retrieved bytes by calling
        compute_reference() and comparing to the stored reference.
        """
        ...

    def compute_reference(self, data: bytes) -> str:
        """Compute the canonical reference for data.

        Only meaningful when content_addressed is True.
        Non-content-addressed tiers must raise NotImplementedError.
        """
        ...

    async def archive(self, soul_data: bytes, soul_id: str,
                      **kwargs: Any) -> ArchiveResult:
        """Archive soul data. Returns an ArchiveResult."""
        ...

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data by reference. Returns raw bytes."""
        ...

    async def verify(self, reference: str) -> bool:
        """Verify that archived data still exists and is accessible."""
        ...
```

Key design decisions:
- **Bytes in, bytes out.** The provider receives the raw `.soul` archive as bytes and
  returns raw bytes on retrieval. It does not parse or interpret the soul data.
- **`tier_name` property.** Each provider declares which tier it represents, enabling
  the system to manage multiple providers simultaneously.
- **`runtime_checkable`.** Implementations can be verified with `isinstance()`.
- **`**kwargs` extensibility.** Provider-specific options (pinning services, gas limits,
  encryption keys) pass through kwargs without polluting the protocol.

### ArchiveResult Model

Returned by `archive()` to describe where the data was stored:

```python
class ArchiveResult(BaseModel):
    tier: str          # "ipfs", "arweave", "blockchain"
    reference: str     # CID, transaction ID, content hash
    url: str = ""      # Human-readable URL (e.g., gateway URL)
    cost: str = "$0.00"
    permanent: bool = False
    archived_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

The `permanent` flag distinguishes between truly permanent storage (Arweave, blockchain)
and pinned-but-evictable storage (IPFS without permanent pinning).

### RecoverySource Model

Represents a location from which a soul can be recovered:

```python
class RecoverySource(BaseModel):
    tier: str
    reference: str
    available: bool = True
    last_verified: datetime = Field(default_factory=datetime.now)
```

The `available` flag is updated by periodic `verify()` calls to ensure the data is
still accessible before attempting recovery.

### Storage Tiers

The protocol defines four standard tier names. Implementations are not limited to these,
but they represent the expected hierarchy:

| Tier | Permanence | Cost | Speed | Status |
|------|-----------|------|-------|--------|
| `local` | Until disk failure | Free | Instant | Implemented |
| `ipfs` | Pinned (evictable) | Low (pinning service) | Seconds | Mock provider |
| `arweave` | Permanent (200+ years) | One-time payment | Minutes | Mock provider |
| `blockchain` | Permanent (chain-dependent) | Gas fees | Minutes-hours | Mock provider |

**Local tier.** Copies the `.soul` file to a designated backup directory. No network
required. The simplest possible eternal storage.

**IPFS tier.** Content-addressed storage via the InterPlanetary File System. Data is
identified by its CID (Content Identifier) -- the hash of the content. Pinning services
(Pinata, web3.storage) keep the data available. Without pinning, data may be garbage
collected.

**Arweave tier.** Permanent storage on the Arweave blockweave. A one-time payment
stores data for 200+ years (by the protocol's economic model). Data is identified by
transaction ID.

**Blockchain tier.** Soul metadata (DID, content hash, timestamp) anchored on a
blockchain for provenance. The full soul data is too large for on-chain storage, so
this tier stores a reference hash that can be used to verify data integrity from
other tiers.

### Content Addressing

All non-local tiers use content addressing: the reference is derived from the data
itself. This provides:

- **Integrity verification.** Re-hash the retrieved data and compare to the reference.
  If they match, the data is unmodified. The `content_addressed` property and
  `compute_reference()` method (added in #293) enable `recover()` to perform this
  check automatically, rejecting substituted data from compromised gateways.
- **Deduplication.** Archiving the same soul state twice produces the same reference.
  No wasted storage.
- **Location independence.** The reference doesn't depend on where the data is stored.
  Multiple gateways, mirrors, or pinning services can serve the same content.

### Multi-Tier Archiving

The runtime supports archiving to multiple tiers simultaneously:

```bash
soul archive aria.soul --tiers local,ipfs
soul recover aria.soul --source ipfs
soul eternal-status aria.soul
```

The manifest tracks eternal storage references:

```json
{
  "eternal": {
    "ipfs": { "cid": "QmYwAPJz...", "pinned_at": "2026-03-07T12:00:00" },
    "arweave": { "txId": "abc123...", "cost": "$0.002" },
    "blockchain": {}
  }
}
```

Recovery attempts tiers in order of reliability: blockchain reference for verification,
Arweave for permanent retrieval, IPFS for fast retrieval, local as last resort.

### Archive/Recover Flow

```
ARCHIVE:
  .soul file (bytes)
    --> EternalStorageProvider.archive(data, soul_id)
    --> Provider uploads to storage network
    --> Returns ArchiveResult (reference, cost, permanence)
    --> Reference stored in manifest.json eternal links

RECOVER:
  soul_id + reference
    --> EternalStorageProvider.verify(reference)  # check availability
    --> EternalStorageProvider.retrieve(reference) # download bytes
    --> Unpack .soul file from bytes
    --> Reconstruct Soul instance

VERIFY:
  reference
    --> EternalStorageProvider.verify(reference)
    --> Returns True if data still accessible
    --> Update RecoverySource.available and last_verified
```

## Implementation Notes

- Spec protocol: `src/soul_protocol/spec/eternal/protocol.py`
- Spec exports: `src/soul_protocol/spec/__init__.py` (ArchiveResult, EternalStorageProvider, RecoverySource)
- Runtime eternal storage: `src/soul_protocol/runtime/` (mock providers)
- CLI commands: `soul archive`, `soul recover`, `soul eternal-status`
- Manifest eternal links: `schemas/SoulManifest.schema.json` (EternalLinks sub-schema)

## Alternatives Considered

**Direct database replication.** Replicate soul data across managed databases (S3,
Cloud SQL, etc.). Reliable but centralized -- the user depends on the platform
operator to maintain the replicas.

**Git-based versioning.** Store soul state in a git repository with each interaction
as a commit. Provides version history and distribution via git remotes, but the
overhead of git operations per interaction is impractical.

**BitTorrent/magnet links.** Peer-to-peer distribution with content addressing. Good
for sharing but no permanence guarantees -- data disappears when all seeders go offline.

**Filecoin.** Similar to IPFS but with economic incentives for storage providers.
Could be a fifth tier. The protocol is extensible enough to support it without
changes to the spec.

## Open Questions

1. **Which providers first?** IPFS has the largest ecosystem and lowest barrier to
   entry (free pinning tiers available). Arweave offers true permanence but requires
   AR tokens. Should the first production provider be IPFS with Pinata/web3.storage,
   or Arweave with Bundlr?

2. **Cost model.** Who pays for eternal storage? The user? The platform? A DAO?
   Should the protocol define a cost estimation interface
   (`async def estimate_cost(data_size: int) -> str`)?

3. **Redundancy requirements.** Should the protocol recommend a minimum number of
   storage tiers? Storing in only one tier is a single point of failure. Requiring
   at least local + one decentralized tier would improve durability.

4. **Encryption before archiving.** Eternal storage is public by default (anyone with
   the CID can retrieve IPFS data). Should the protocol require encryption before
   archiving to public storage? The runtime already has Fernet encryption in
   `crypto/encrypt.py`. See also RFC-004 encryption discussion.

5. **Garbage collection.** IPFS data is garbage collected if not pinned. Should the
   protocol define a re-pinning strategy? Periodic `verify()` calls that trigger
   re-archiving if data becomes unavailable?

6. **Soul size limits.** Large souls (10K+ memories) could be expensive to archive.
   Should the protocol define a compression or summarization step before archiving
   to reduce costs? Or should large souls use a different strategy (store the delta,
   not the full state)?

7. **Verification frequency.** How often should `verify()` be called? Every session?
   Daily? Only on explicit user request? Frequent verification adds network overhead
   but catches availability issues early.

## References

- [IPFS Documentation](https://docs.ipfs.tech/)
- [Arweave Whitepaper](https://www.arweave.org/whitepaper.pdf)
- [W3C Decentralized Identifiers](https://www.w3.org/TR/did-core/) -- DID integration with eternal references
- [Content Addressable Storage](https://en.wikipedia.org/wiki/Content-addressable_storage)
- `src/soul_protocol/spec/eternal/protocol.py` -- EternalStorageProvider protocol
- `schemas/SoulManifest.schema.json` -- EternalLinks sub-schema
