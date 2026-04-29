---
{
  "title": "InMemoryStorage: Dict-Backed Soul Backend for Tests and Ephemeral Processes",
  "summary": "`InMemoryStorage` is a zero-dependency, dict-backed implementation of `StorageProtocol` for unit tests and short-lived processes. All methods are `async` to satisfy the protocol interface, even though no I/O occurs.",
  "concepts": [
    "InMemoryStorage",
    "StorageProtocol",
    "unit testing",
    "ephemeral storage",
    "dict backend",
    "async interface",
    "SoulConfig",
    "protocol compliance"
  ],
  "categories": [
    "runtime",
    "storage",
    "testing"
  ],
  "source_docs": [
    "6caba7ee6fc06da8"
  ],
  "backlinks": null,
  "word_count": 489,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`InMemoryStorage` is a zero-dependency, dict-backed implementation of `StorageProtocol` designed for unit tests and short-lived processes. All methods are `async` to satisfy the protocol interface, even though no actual I/O occurs. Souls live only in a plain Python `dict` keyed by `soul_id` and are garbage-collected when the instance goes out of scope.

## Why It Exists

Test suites that use `FileStorage` face three problems that `InMemoryStorage` eliminates:

1. **State bleeding between tests** — a soul written to disk in one test can persist and affect subsequent tests if teardown is incomplete. `InMemoryStorage` instances are isolated by default: create a new instance per test, and state never leaks.
2. **Slow I/O** — disk writes are orders of magnitude slower than dict inserts. In a suite of hundreds of soul-related tests, `InMemoryStorage` can reduce fixture setup time from seconds to milliseconds.
3. **Platform sensitivity** — path sanitization, file permissions, and temp directory behavior vary between macOS, Linux, and Windows. `InMemoryStorage` removes all of these variables from test results.

## Interface

```python
storage = InMemoryStorage()

# Save (path param is accepted but ignored)
await storage.save("my-soul", config)

# Load — returns None if not found, never raises
config = await storage.load("my-soul")

# Delete — idempotent, returns True if existed
existed = await storage.delete("my-soul")

# List all stored IDs
soul_ids = await storage.list_souls()
```

## Protocol Compliance

All methods are `async` to satisfy `StorageProtocol` structurally. This makes `InMemoryStorage` a transparent swap for `FileStorage` in async test contexts — no `asyncio.run()` wrappers or sync adapters required.

The `path` parameter on `save` and `load` is accepted but silently ignored. This is consistent with the protocol's contract where `path: Path | None` is always optional. In-memory storage has no concept of a base directory.

`load` returns `None` (not raises) when a soul is not found, matching `FileStorage`'s behavior. Tests can assert `config is None` rather than catching exceptions.

`delete` returns `True` if the soul existed and was removed, `False` if it was already absent. This idempotent contract lets callers clean up without needing to check existence first.

## Isolation Pattern for Tests

```python
@pytest.fixture
def storage():
    return InMemoryStorage()  # fresh instance per test

async def test_save_and_load(storage):
    await storage.save("alice", config)
    loaded = await storage.load("alice")
    assert loaded.identity.name == "alice"
```

Each test gets a fresh `InMemoryStorage` with no inherited state.

## Limitations

- **Not thread-safe**: The underlying `dict` is not protected by a lock. Concurrent writes from multiple asyncio tasks may race in edge cases.
- **No memory tier support**: Unlike `save_soul_full`, this backend only stores `SoulConfig`. The seven memory tier dicts are not persisted. Tests needing full memory persistence should combine this with a separate in-memory `MemoryManager`.
- **No persistence across process boundaries**: All souls are lost on process exit — a deliberate feature for ephemeral use.

## Known Gaps

The thread-safety limitation is not documented in the class docstring, which could mislead teams running concurrent async test suites. A note in the docstring would prevent confusion.