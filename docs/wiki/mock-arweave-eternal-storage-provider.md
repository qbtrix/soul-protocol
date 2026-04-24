---
{
  "title": "Mock Arweave Eternal Storage Provider",
  "summary": "`MockArweaveProvider` simulates Arweave's permanent, pay-once storage model using an in-memory dict and deterministic transaction IDs — no gateway required. It lets test suites and local development exercise the full Arweave archive/retrieve/verify cycle without real AR tokens or network access.",
  "concepts": [
    "MockArweaveProvider",
    "Arweave",
    "permanent storage",
    "transaction ID",
    "in-memory mock",
    "eternal storage",
    "cost simulation",
    "EternalStorageProvider",
    "blockchain storage"
  ],
  "categories": [
    "eternal-storage",
    "providers",
    "testing",
    "arweave"
  ],
  "source_docs": [
    "80484b39945c2a2c"
  ],
  "backlinks": null,
  "word_count": 323,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Arweave is a blockchain-based storage network where data is uploaded once and stored permanently. Real integration requires an Arweave wallet, AR tokens, and a running gateway. `MockArweaveProvider` removes all of those dependencies, replacing them with an in-memory store that mirrors Arweave's behavioral contract.

The mock exists so the evolution system, export pipeline, and multi-tier archive logic can be tested end-to-end without external infrastructure.

## Arweave Semantics Preserved

### Transaction IDs Format

```python
def _generate_tx_id(self, data: bytes) -> str:
    self._tx_counter += 1
    seed = f"{time.time_ns()}:{self._tx_counter}:{len(data)}"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return digest[:43]  # Arweave tx IDs are 43 chars
```

Real Arweave transaction IDs are 43-character base64url strings. The mock produces 43-character hex strings from a SHA-256 of a counter+timestamp+length seed. The counter prevents collisions when multiple archives happen within the same nanosecond.

### Cost Simulation

```python
cost_usd = len(soul_data) / 1024 * 0.005
cost_str = f"${cost_usd:.4f}"
```

Arweave charges roughly $0.005 per KB (varies with AR price). The mock simulates this so `ArchiveResult.cost` carries a realistic value. Callers that inspect cost before deciding to archive get believable data during testing.

### Permanence Flag

The mock returns `permanent=True` — matching Arweave's core promise that archived data cannot be deleted. This distinction matters when Soul Protocol's multi-tier storage logic ranks which backends to use for recovery.

## Data Flow

```
archive(soul_data, soul_id)
  → _generate_tx_id(soul_data) — counter + time + length → SHA-256 → 43 chars
  → _store[tx_id] = soul_data
  → ArchiveResult(tier="arweave", reference=tx_id, permanent=True, cost=...)

retrieve(reference)  [reference IS the tx_id here]
  → _store[tx_id] → bytes or KeyError

verify(reference)
  → tx_id in _store
```

## Known Gaps

- Transactions are stored per-instance. Across test cases, if a new `MockArweaveProvider` is instantiated, all prior archives are lost. Tests that need cross-instance persistence must use `LocalStorageProvider` instead.
- No simulation of Arweave's confirmation delay (real Arweave takes ~2 minutes to confirm a transaction). If the production implementation ever adds a `wait_for_confirmation` step, the mock will need a `pending` state.