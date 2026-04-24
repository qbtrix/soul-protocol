---
{
  "title": "Test Suite for Soul Error Handling",
  "summary": "Verifies that Soul's three main lifecycle operations — awaken(), export(), and retire() — raise specific, descriptive exception types rather than raw Python exceptions. Also tests exception class structure to ensure callers can extract actionable information like file paths and failure reasons.",
  "concepts": [
    "error handling",
    "SoulFileNotFoundError",
    "SoulCorruptError",
    "SoulExportError",
    "SoulRetireError",
    "awaken",
    "export",
    "retire",
    "exception hierarchy",
    "atomic state change",
    "Windows compatibility"
  ],
  "categories": [
    "testing",
    "error handling",
    "soul lifecycle",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "66e16f346344c034"
  ],
  "backlinks": null,
  "word_count": 528,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_error_handling.py` tests the error boundary layer for `Soul.awaken()`, `Soul.export()`, and `Soul.retire()`. The core design principle is that callers should never see raw Python exceptions like `FileNotFoundError`, `BadZipFile`, or `PermissionError` — instead, they get soul-specific exception types with structured fields. This matters because soul files are user-facing: a good error message says "No soul file at /path/to/soul.soul" rather than "No such file or directory".

## Exception Taxonomy

The suite implicitly documents the exception hierarchy:
- `SoulFileNotFoundError` — path does not exist or is not a recognized format
- `SoulCorruptError` — file exists but is not a valid soul archive
- `SoulExportError` — export failed due to I/O issues (permissions, disk full)
- `SoulRetireError` — retire failed, with rollback to preserve soul state

All inherit from a common base class (`TestExceptionClasses.test_all_exceptions_inherit_from_base`).

## awaken() Error Handling

```python
async def test_awaken_nonexistent_file_raises_soul_file_not_found(self):
    with pytest.raises(SoulFileNotFoundError, match="No soul file at"):
        await Soul.awaken("/tmp/does_not_exist_12345.soul")
```

The `match` parameter is intentional — it checks that the error message includes a human-readable description, not just the exception type. `test_awaken_error_includes_path` goes further: it confirms that `exc_info.value.path` is set to the exact path passed in, so callers can programmatically construct error messages or retry with a different path.

Corrupt files produce `SoulCorruptError`, not a raw `zipfile.BadZipFile`. The distinction is important for callers that need to distinguish "file missing" from "file damaged".

`test_awaken_unknown_format_still_raises_value_error` verifies that unsupported extensions (`.xyz`) raise `ValueError` — not silently absorbed — preserving the fast-fail contract for programming errors.

## export() Error Handling

```python
@pytest.mark.skipif(_IS_WINDOWS, reason="chmod-based tests not supported on Windows")
async def test_export_to_readonly_dir_raises_soul_export_error(self):
    # make directory read-only, attempt export, expect SoulExportError
```

The skip guard reflects a real portability constraint: `chmod` permission manipulation does not work on Windows. Rather than making the test lie (always-pass on Windows), it is explicitly skipped — this is the correct behavior and the test correctly documents the limitation.

## retire() Error Handling

Retire is the most subtle: it must be **atomic with respect to state change**. If saving fails, the soul must still be in its pre-retire state:

```python
async def test_retire_keeps_lifecycle_on_save_failure(self):
    # Mock save() to raise, call retire(), assert lifecycle hasn't changed
    with patch.object(soul, "_save", side_effect=OSError("disk full")):
        with pytest.raises(SoulRetireError):
            await soul.retire()
    assert soul.lifecycle != "retired"  # state must be rolled back
```

Without this test, a buggy implementation could mark the soul as retired in memory but fail to persist, leaving the soul in an inconsistent state across a restart.

`test_retire_without_preserve_skips_save` tests the `preserve=False` path — when the caller explicitly says "don't save a copy", the save step is skipped entirely, which means a save failure cannot occur.

## Exception Class Structure

```python
def test_soul_file_not_found_has_path(self):
    exc = SoulFileNotFoundError("/some/path.soul")
    assert exc.path == "/some/path.soul"

def test_soul_corrupt_has_path_and_reason(self):
    exc = SoulCorruptError("/some/path.soul", "Invalid zip")
    assert exc.path == "/some/path.soul"
    assert exc.reason == "Invalid zip"
```

Structured fields (not just message strings) allow downstream tooling to handle errors programmatically — for example, a CLI can format `exc.path` in bold, or an MCP server can include it in a structured error response.

## Known Gaps

The `_IS_WINDOWS` guard is a known gap in cross-platform coverage. The permission-based export failure test is skipped on Windows, meaning Windows users have slightly less error-handling coverage for that specific failure mode.
