---
{
  "title": "Mock Blockchain Soul Registry Provider",
  "summary": "`MockBlockchainProvider` simulates an on-chain soul registry where each soul is minted as a unique NFT-like token with a hash-based token ID. It enables testing of blockchain-based soul identity ownership without a real wallet, chain, or gas fees.",
  "concepts": [
    "MockBlockchainProvider",
    "blockchain registry",
    "soul NFT",
    "token minting",
    "on-chain identity",
    "soul_id",
    "token_id",
    "EternalStorageProvider",
    "chain name"
  ],
  "categories": [
    "eternal-storage",
    "providers",
    "testing",
    "blockchain"
  ],
  "source_docs": [
    "eff9233c75584359"
  ],
  "backlinks": null,
  "word_count": 345,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The blockchain tier in Soul Protocol represents proof of identity ownership — a soul's existence recorded immutably on-chain, similar to how NFTs prove digital asset ownership. `MockBlockchainProvider` lets tests verify the entire lifecycle (mint → store → retrieve → verify) without deploying smart contracts or spending gas.

## Blockchain Semantics Preserved

### Token Minting Model

```python
def _mint_token_id(self, soul_id: str) -> str:
    self._token_counter += 1
    seed = f"{self._chain_name}:{soul_id}:{self._token_counter}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:16]
    return f"0x{digest}"
```

Each soul gets a unique token prefixed with `0x` to mimic Ethereum hex addresses. The seed includes the chain name, soul_id, a monotonic counter, and nanosecond timestamp. This prevents collisions and mimics how on-chain addresses are derived.

### Per-Soul Token Registry

```python
self._registry: dict[str, bytes] = {}   # token_id → data
self._soul_tokens: dict[str, str] = {}  # soul_id → token_id
```

The mock maintains two maps: a registry of token ID to raw data, and a reverse index from soul_id to token_id. This mirrors a real soul registry contract that maps wallet/DID to token. The `retrieve()` method uses the soul_id → token_id → data path, matching how a contract `ownerOf()` + data fetch would work.

### Configurable Chain Name

```python
def __init__(self, chain_name: str = "mock-chain") -> None:
```

The chain name is incorporated into token ID generation and the returned reference. This lets tests instantiate providers for different named chains (`"ethereum"`, `"polygon"`, etc.) and verify that references are chain-scoped — preventing accidental cross-chain lookups.

## Data Flow

```
archive(soul_data, soul_id)
  → _mint_token_id(soul_id) → "0x<16-char hex>"
  → _registry[token_id] = soul_data
  → _soul_tokens[soul_id] = token_id
  → ArchiveResult(tier="blockchain", reference="<chain>:<soul_id>:<token_id>", permanent=True)

retrieve(reference)
  → parse soul_id from reference
  → token_id = _soul_tokens[soul_id]
  → _registry[token_id]

verify(reference)
  → soul_id in _soul_tokens and token_id in _registry
```

## Known Gaps

- In-memory only — data is lost when the provider instance is garbage collected.
- No simulation of gas costs. Real blockchain archival would carry a cost estimate in `ArchiveResult.cost`.
- No re-mint guard: archiving the same `soul_id` twice mints a new token without burning the old one, which does not match most NFT registry patterns.