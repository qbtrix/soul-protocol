---
{
  "title": "StorageProtocol: Runtime-Checkable Interface for Soul Storage Backends",
  "summary": "`StorageProtocol` is a `@runtime_checkable` Python `Protocol` that defines the four operations all soul storage backends must implement: `save`, `load`, `delete`, and `list_souls`. It decouples the runtime from any specific storage implementation, enabling `FileStorage` and `InMemoryStorage` to be swapped without modifying callers.",
  "concepts": [
    "StorageProtocol",
    "runtime_checkable",
    "Protocol",
    "save",
    "load",
    "delete",
    "list_souls",
    "backend abstraction",
    "dependency inversion",
    "SoulConfig"
  ],
  "categories": [
    "runtime",
    "storage",
    "protocol design"
  ],
  "source_docs": [
    "ef42651d44b5f82b"
  ],
  "backlinks": null,
  "word_count": 500,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`StorageProtocol` is a `@runtime_checkable` Python `Protocol` that defines the four operations every soul storage backend must implement: `save`, `load`, `delete`, and `list_souls`. It decouples the soul runtime from any specific storage implementation, making backends interchangeable without modifying the code that uses them.

## Why a Protocol Rather Than an Abstract Base Class

Using `typing.Protocol` instead of an abstract base class (ABC) means third-party backends can satisfy the interface without importing anything from `soul_protocol`. A hypothetical `S3Storage` or `RedisStorage` only needs to implement the four method signatures — no `class S3Storage(StorageProtocol)` required. This is structural subtyping (duck typing with type-system support), which is the idiomatic Python approach for plugin interfaces.

The `@runtime_checkable` decorator enables `isinstance(backend, StorageProtocol)` checks at runtime. This is used in factory functions and test harnesses to verify that a provided backend satisfies the interface before wiring it into the runtime.

## Interface

```python
@runtime_checkable
class StorageProtocol(Protocol):
    async def save(self, soul_id: str, config: SoulConfig, path: Path | None = None) -> None:
        ...

    async def load(self, soul_id: str, path: Path | None = None) -> SoulConfig | None:
        ...

    async def delete(self, soul_id: str) -> bool:
        ...

    async def list_souls(self) -> list[str]:
        ...
```

## Method Contracts

### save
Persists a `SoulConfig` keyed by `soul_id`. The `path` parameter is optional — backends that ignore it (like `InMemoryStorage`) still satisfy the protocol. All methods are `async` because production backends (filesystem, cloud storage) are inherently I/O-bound.

### load
Returns `SoulConfig | None`. Returning `None` for absent souls rather than raising a `KeyError` or `FileNotFoundError` is a deliberate choice: callers in async pipelines check for absence without try/except blocks, which is more readable and composable.

### delete
Returns `True` if the soul existed and was removed, `False` if it was already absent. This idempotent contract prevents callers from needing to `load` before `delete` to avoid errors. It also makes delete safe to call in cleanup code without knowing whether the soul exists.

### list_souls
Returns all stored soul IDs. This enables administrative operations — listing, migrating, and auditing souls — without coupling to filesystem or database details.

## Decoupling Benefit

The runtime's `Soul` class and CLI commands accept a `StorageProtocol`-compatible backend, never a concrete class. This means:

- Tests pass `InMemoryStorage()` — no disk I/O, no cleanup.
- Production passes `FileStorage(base_dir=Path.home() / ".soul")` — full persistence.
- Custom backends (encrypted storage, cloud object stores, databases) can be plugged in without modifying any runtime code.

## Runtime Checking Pattern

```python
if not isinstance(backend, StorageProtocol):
    raise TypeError(f"Expected StorageProtocol, got {type(backend)}")
```

The `@runtime_checkable` flag makes this check reliable for the four declared methods. Note that `runtime_checkable` only checks for method presence, not signatures — a class with a `save` attribute that is not a coroutine would still pass the `isinstance` check.

## Known Gaps

The protocol does not define a bulk operation (e.g., `load_many`, `migrate`). Callers needing bulk access must call `list_souls()` then `load()` in a loop, which is inefficient for large soul catalogs. A `list_souls_with_configs()` method would be a natural addition.