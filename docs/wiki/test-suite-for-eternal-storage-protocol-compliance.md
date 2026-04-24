---
{
  "title": "Test Suite for Eternal Storage Protocol Compliance",
  "summary": "Verifies that all eternal storage providers satisfy the EternalStorageProvider protocol at runtime, and validates the Pydantic models ArchiveResult and RecoverySource for field defaults, full construction, and serialization round-trips.",
  "concepts": [
    "EternalStorageProvider",
    "protocol compliance",
    "ArchiveResult",
    "RecoverySource",
    "Pydantic",
    "tier name",
    "isinstance check",
    "structural protocol",
    "PEP 544",
    "mock providers"
  ],
  "categories": [
    "testing",
    "eternal storage",
    "protocol",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "42b6018d5c5b65c3"
  ],
  "backlinks": null,
  "word_count": 457,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_protocol.py` has two distinct purposes: it validates the data models used in the eternal storage protocol (`ArchiveResult`, `RecoverySource`), and it confirms that every concrete provider class (`MockIPFSProvider`, `MockArweaveProvider`, `MockBlockchainProvider`, `LocalStorageProvider`) satisfies the `EternalStorageProvider` protocol. Protocol compliance tests catch the case where a new provider is added that is missing required methods.

## Data Model Tests

### `TestArchiveResultModel`

`ArchiveResult` is the return type of every `provider.archive()` call. The tests establish the full field contract:

```python
def test_create_minimal(self):
    result = ArchiveResult(tier="ipfs", reference="bafytest123")
    assert result.cost == "$0.00"       # default: free (local/mock)
    assert result.permanent is False    # default: not permanent
    assert result.url == ""             # default: no URL
    assert result.metadata == {}        # default: empty
```

Default values matter because providers must be able to return minimal results without specifying every field. A provider that only knows the tier and reference (e.g., a fast archive that resolves metadata asynchronously) should not be forced to populate fields it doesn't have yet.

`test_create_full` confirms the Arweave-style result shape: `permanent=True`, a cost string like `"$0.0050"`, and a URL pointing to the public gateway.

`test_serialization_roundtrip` verifies that `model_dump()` followed by `model_validate()` produces an equivalent object. This is critical for persistence — archive results are stored in the manager's internal recovery source registry and must survive serialization.

### `TestRecoverySourceModel`

`RecoverySource` represents a known location from which a soul can be recovered:

```python
def test_create_default(self):
    source = RecoverySource(tier="ipfs", reference="bafytest")
    assert source.available is True  # default: assume available
```

`available=False` is the mechanism by which the manager marks a source as known-bad before attempting recovery. Testing the default (`True`) confirms that newly created sources are optimistically available.

## Protocol Compliance Tests

```python
class TestProtocolCompliance:
    def test_mock_ipfs_is_provider(self):
        provider = MockIPFSProvider()
        assert isinstance(provider, EternalStorageProvider)
```

Python structural protocols (PEP 544) do not automatically enforce that a class implements all required methods — `isinstance()` against a `Protocol` only works if the class declares the right methods with the right signatures. These tests confirm that each provider class passes the `isinstance` check, catching missing method implementations at development time rather than at runtime when the manager tries to call them.

`test_tier_names` verifies that each provider returns the canonical lowercase tier identifier from `tier_name`:

```python
assert MockIPFSProvider().tier_name == "ipfs"
assert MockArweaveProvider().tier_name == "arweave"
assert MockBlockchainProvider().tier_name == "blockchain"
```

The manager uses `provider.tier_name` as the dictionary key when registering providers. A mismatch (e.g., `"IPFS"` vs `"ipfs"`) would cause silent registration under a wrong key, making the tier unreachable by its canonical name.

## Known Gaps

No TODO markers. The `LocalStorageProvider` tier name is tested (`test_tier_names` references `tmp_path`), though the partial source text is cut off. The tests do not verify that the protocol's async method signatures match (only that the methods exist), so a provider with wrong argument signatures would still pass.
