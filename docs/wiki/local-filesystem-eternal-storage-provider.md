---
{
  "title": "Local Filesystem Eternal Storage Provider",
  "summary": "`LocalStorageProvider` archives soul data as files on the local filesystem using a hash-based naming scheme to avoid collisions. It serves as the most basic, always-available eternal storage tier — no network, no external dependency — making it suitable for development, offline use, and as a fast local cache alongside remote backends.",
  "concepts": [
    "LocalStorageProvider",
    "filesystem storage",
    "soul archive",
    "hash-based filenames",
    "idempotent archive",
    "lazy directory creation",
    "EternalStorageProvider",
    "content hash",
    "local tier"
  ],
  "categories": [
    "eternal-storage",
    "providers",
    "local-storage"
  ],
  "source_docs": [
    "a50958694fb6cdf9"
  ],
  "backlinks": null,
  "word_count": 352,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`LocalStorageProvider` is the simplest eternal storage backend: it writes `.soul` archive files to disk. It implements the `EternalStorageProvider` protocol, giving it the same interface as IPFS, Arweave, or blockchain providers, while requiring nothing beyond a writable directory.

Its primary job is to guarantee that soul data is never lost during development or when the user has no network access. Every soul that gets archived here is immediately retrievable without any external service.

## Architecture and Key Decisions

### Lazy Directory Creation

```python
async def archive(self, soul_data: bytes, soul_id: str, **kwargs) -> ArchiveResult:
    self._base_dir.mkdir(parents=True, exist_ok=True)
    ...
```

The `~/.soul/eternal/local/` directory is **not** created in `__init__`. This is intentional: if you construct a `LocalStorageProvider` but never archive anything, no directory is created on disk. This avoids cluttering the filesystem for callers that instantiate the provider speculatively.

### Deterministic Reference Generation

```python
def _ref_for(self, soul_data: bytes, soul_id: str) -> str:
    content_hash = hashlib.sha256(soul_data).hexdigest()[:16]
    return f"local:{soul_id}:{content_hash}"
```

References encode both `soul_id` (ownership) and a content hash truncated to 16 hex chars (collision avoidance). This means archiving the same soul twice produces the same reference — **idempotent by design**. The archive is overwritten rather than duplicated, keeping the directory clean.

### Filesystem-Safe Path Encoding

```python
def _path_for(self, reference: str) -> Path:
    safe_name = reference.replace(":", "_").replace("/", "_")
    return self._base_dir / f"{safe_name}.soul"
```

The reference string contains colons (separating tier, soul_id, and hash). Since colons are not valid in filenames on Windows and cause issues in some shells, they are replaced with underscores before constructing the path.

## Data Flow

```
archive(soul_data, soul_id)
  → _ref_for() → deterministic reference string
  → mkdir(parents=True, exist_ok=True) [lazy]
  → _path_for() → safe filesystem path
  → write bytes to path
  → return ArchiveResult(tier="local", reference=..., permanent=False)

retrieve(reference)
  → _path_for(reference)
  → read bytes from path

verify(reference)
  → _path_for(reference).exists()
```

## Known Gaps

- `permanent=False` in `ArchiveResult` is correct — local files can be deleted. True permanence requires Arweave or equivalent.
- No content integrity check on `retrieve()` — the stored bytes are returned as-is without re-verifying the hash embedded in the reference. A corrupt write would go undetected until the unpacker raises a validation error.