---
{
  "title": "Soul Protocol Custom Exception Hierarchy",
  "summary": "`exceptions.py` defines the typed exception hierarchy for soul-protocol operations, covering file-not-found, corruption, export failures, encryption errors, and protected role violations. Using typed exceptions instead of bare `Exception` lets callers write precise `except` clauses and present actionable error messages to users.",
  "concepts": [
    "SoulProtocolError",
    "SoulFileNotFoundError",
    "SoulCorruptError",
    "SoulExportError",
    "SoulEncryptedError",
    "SoulDecryptionError",
    "SoulProtectedError",
    "SoulRetireError",
    "exception hierarchy",
    "governance soul",
    "typed exceptions"
  ],
  "categories": [
    "exceptions",
    "error-handling",
    "security",
    "governance"
  ],
  "source_docs": [
    "736728741a43657c"
  ],
  "backlinks": null,
  "word_count": 401,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

When a soul operation fails, the caller needs to know *why*. A bare `Exception` with a string message forces callers to parse error text — fragile and unreadable. Soul Protocol instead raises typed exceptions so callers can branch on the specific failure mode.

```python
class SoulProtocolError(Exception): ...  # base
```

All errors inherit from `SoulProtocolError`, which means a catch-all `except SoulProtocolError` is always available as a safety net.

## Exception Taxonomy

| Exception | Trigger | Key Fields |
|---|---|---|
| `SoulFileNotFoundError` | `awaken()` called with a non-existent path | `path` |
| `SoulCorruptError` | ZIP archive invalid or cannot be parsed | `path`, `reason` |
| `SoulExportError` | `export()` fails (disk full, permissions) | `path`, `reason` |
| `SoulRetireError` | `retire()` fails because memory preservation failed | `reason` |
| `SoulEncryptedError` | Loading an encrypted `.soul` without a password | `soul_name` |
| `SoulDecryptionError` | Wrong password or corrupted ciphertext during decrypt | `reason` |
| `SoulProtectedError` | Attempting to delete/retire a protected governance soul | `name`, `role`, `path` |

## Defensive Design Patterns

### Constructors Embed Context

Each exception constructor accepts the context needed to produce a useful message:

```python
class SoulFileNotFoundError(SoulProtocolError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No soul file at {path}")
```

The `path` attribute is stored on the exception object, not just in the string. CLI handlers and test assertions can access `exc.path` directly without string parsing.

### Encryption Error Separation

`SoulEncryptedError` and `SoulDecryptionError` are intentionally separate. The first means "you didn't try to decrypt" — the fix is to provide a password. The second means "you tried but failed" — the fix is to try a different password or recover from backup. Merging these would force callers to parse the message to distinguish the cases.

### Governance Protection

`SoulProtectedError` was added alongside the org governance RFC. Root governance souls (the top-level authority soul in an org hierarchy) cannot be deleted or retired — doing so would be catastrophic for org integrity. Rather than silently ignoring the operation or using a boolean flag, the system raises `SoulProtectedError` with the soul's name, role, and path, making the violation explicit and auditable.

## Known Gaps

- No `SoulMigrationError` for platform migration failures — currently migration errors fall back to generic `SoulProtocolError`.
- `SoulRetireError` carries only `reason` as a string. Adding a `memory_tier` field would help callers understand which memory tier failed to preserve.