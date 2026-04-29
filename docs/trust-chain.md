# Trust Chain — verifiable action history

The trust chain is a soul's append-only signed log of every audit-worthy action it has performed. It is the cryptographic proof of what a soul learned, when, and from whom.

This page covers:

- [Why a trust chain](#why-a-trust-chain)
- [Threat model — what it does and doesn't protect](#threat-model)
- [What is signed, what isn't](#what-is-signed-what-isnt)
- [Verifying a chain externally](#verifying-a-chain-externally)
- [Key management](#key-management)
- [Sharing a soul without leaking the signing key](#sharing-a-soul-without-leaking-the-signing-key)
- [On-disk layout](#on-disk-layout)
- [API quick reference](#api-quick-reference)

## Why a trust chain

A soul that carries memories across sessions, devices, and platforms only matters if its history can be trusted. Without a verifiable chain, a soul's claims about what it learned are just claims — anyone with file write access can rewrite the past.

The trust chain closes that gap. Every learning event, memory mutation, evolution step, and bond change appends a signed entry. Each entry references the previous one's hash, so altering any entry invalidates every entry after it. Verification with `soul verify` runs in milliseconds and either accepts the chain whole or points at the first broken entry.

This is the foundation we need for:

- **Reputation systems** — agents can verify each other's history before trusting recommendations
- **Provenance proofs** — a soul can prove that a specific learning event preceded a specific decision
- **Regulated deployments** — compliance regimes that require an immutable audit trail
- **Cross-platform migration** — when a soul moves from one runtime to another, the destination can verify nothing was injected during transit

## Threat model

The trust chain protects against:

| Threat | How it's caught |
|---|---|
| Tampering with a past entry's content | Hash chain breaks; `verify_chain()` returns False at the changed entry |
| Forging a signature without the private key | Signature verification fails using the embedded public key |
| Inserting a fake entry in the middle | The next entry's `prev_hash` no longer matches; chain breaks |
| Reordering entries | Sequence numbers go non-monotonic; chain breaks |
| Replaying genesis entry | Duplicate seq detected by `verify_chain()` |
| Backdating entries | Future-timestamped entries (>60s skew) are flagged; backdated entries can pass timestamp checks but break the hash chain when inserted |

The trust chain does **not** protect against:

| Limit | What you need instead |
|---|---|
| Truncation (lopping off the most recent N entries) | A receiver-side policy that pins the latest known head externally — out of scope for the chain itself |
| Compromise of the soul's private key | Once leaked, an attacker can append valid entries; rotate keys and republish |
| Censorship of which entries get appended in the first place | The chain only attests to what was signed; it cannot force a soul to record a given action |
| Confidentiality of payload content | Payloads are stored as hashes only — see [What is signed](#what-is-signed-what-isnt). The actual memory contents live in their own tier files, which are protected by the soul's encryption layer (`Soul.export(password=...)`) |
| External-time correctness | The chain records the soul's local clock, not a trusted time authority. Use a notary or timestamping service if you need external-time anchoring |

## What is signed, what isn't

Every `TrustEntry` contains:

```
seq           — monotonic 0-indexed position in the chain
timestamp     — UTC time the entry was signed
actor_did     — DID of the signer (usually the soul's own DID)
action        — dot-namespaced action name (memory.write, evolution.applied, …)
payload_hash  — SHA-256 hex of canonical JSON of the action's payload
prev_hash     — SHA-256 hex of the previous entry, or GENESIS_PREV_HASH
signature     — Ed25519 signature (base64) over the canonical JSON of the entry minus signature
algorithm     — "ed25519"
public_key    — base64 of the raw 32-byte public key, embedded so verifiers don't need an external key registry
```

What is NOT in the chain:

- **The actual payload contents.** Only `payload_hash`. So a chain entry says "the soul wrote 3 memories with IDs `m1, m2, m3`" — not the text of those memories. The text lives in `memory/episodic.json` etc., outside the chain.
- **PII or content from the user side.** If the action.payload had a user's email in it, only the hash of the JSON containing that email is on chain. The hash is not reversible.
- **Recall results.** Recall is read-only — it doesn't mutate state, so it doesn't need a chain entry. (You can layer a separate retrieval-trace receipt on top via `RetrievalTrace`.)

This is intentional: the chain stays compact (kilobytes per thousand entries instead of megabytes), and verification only needs the action sequence, not the action data.

## Verifying a chain externally

The simplest path is the CLI:

```bash
soul verify path/to/soul          # exits 0 on valid, 1 on tampering
soul verify path/to/soul --json   # machine-readable output
```

For programmatic verification:

```python
from soul_protocol.runtime.soul import Soul

soul = await Soul.awaken("path/to/soul")
valid, reason = soul.verify_chain()
if not valid:
    raise RuntimeError(f"Chain tampered: {reason}")
```

Or directly from the spec layer (no runtime needed) when you only have the chain JSON:

```python
from soul_protocol.spec.trust import TrustChain, verify_chain

chain = TrustChain.model_validate_json(chain_json_bytes)
valid, reason = verify_chain(chain)
```

The spec-layer verification path requires only `pydantic` and `cryptography` — both already in the base install. No private keys are needed; every entry carries its own public key.

## Key management

Each soul owns an Ed25519 keypair. The keys live under `keys/` inside the soul archive or directory:

```
keys/
  public.key   — raw 32 bytes, always present after first save
  private.key  — raw 32 bytes, present only when explicitly retained
```

The keypair is generated on first `Soul.birth()` and persists across saves and awakens. To regenerate a soul's identity (a destructive operation that breaks all prior chain verification), build a new soul from scratch — the trust chain has no in-protocol key rotation.

Verification needs only the public key, and every chain entry already embeds a copy of the public key it was signed under. So a soul shared without `private.key` is still verifiable — just not extensible.

## Sharing a soul without leaking the signing key

Use `Soul.export(path, include_keys=False)` (the default). This drops `keys/private.key` from the archive but keeps `keys/public.key` and the full `trust_chain/`. The recipient can:

- Read the chain
- Verify the chain
- Awaken the soul and inspect memories

The recipient cannot:

- Append new chain entries under the original soul's DID (no private key)
- Sign anything that would pass `verify_chain()` against the original public key

When the recipient calls `Soul.observe()` or any other state-changing method on a soul loaded without a private key, the underlying action still happens (memory writes, bond updates) but **no chain entry is appended**. The recipient's chain stays at the length it was when received.

If you want to give the recipient the signing key — for instance migrating between your own devices — pass `include_keys=True`:

```python
await soul.export("backup.soul", include_keys=True)  # only do this on trusted destinations
```

`Soul.save()` and `Soul.save_local()` default to `include_keys=True` because they're meant for the owner's own machine. `Soul.export()` defaults to `include_keys=False` because exports are usually for sharing.

## On-disk layout

In a `.soul` zip archive or a `.soul/` directory:

```
trust_chain/
  chain.json         — canonical Pydantic-serialized TrustChain (the source of truth on load)
  entry_000.json     — human-readable copy of seq 0
  entry_001.json     — human-readable copy of seq 1
  ...
keys/
  public.key
  private.key        — only when include_keys=True
```

The per-entry JSON files are for human inspection and debugging — `chain.json` is what the runtime reads. Chains are not encrypted independently of the soul; if the surrounding soul archive is password-encrypted (`Soul.export(password=...)`), the chain entries are encrypted at rest too.

## API quick reference

Spec layer (`soul_protocol.spec.trust`):

- `TrustEntry`, `TrustChain` — Pydantic models
- `SignatureProvider` — Protocol; runtime supplies an Ed25519 implementation
- `verify_entry(entry, prev_entry, provider=None) -> bool`
- `verify_chain(chain) -> tuple[bool, str | None]`
- `chain_integrity_check(chain) -> dict` — `{valid, length, first_failure, signers}`
- `compute_payload_hash(payload) -> str`
- `compute_entry_hash(entry) -> str`
- `GENESIS_PREV_HASH` — `"0" * 64`

Runtime layer:

- `soul_protocol.runtime.crypto.ed25519.Ed25519SignatureProvider`
- `soul_protocol.runtime.crypto.keystore.Keystore`
- `soul_protocol.runtime.trust.manager.TrustChainManager`

Soul-level convenience:

- `soul.trust_chain` — read-only `TrustChain`
- `soul.trust_chain_manager` — `TrustChainManager` for advanced use
- `soul.verify_chain()` → `(valid, reason)`
- `soul.audit_log(action_prefix=None, limit=None)` → `list[dict]`

CLI:

- `soul verify <path>` — exit 0/1
- `soul audit <path> --filter memory. --limit 20` — Rich table or `--json`

MCP tools:

- `soul_verify` — JSON `{soul, did, valid, length, signers, first_failure}`
- `soul_audit` — JSON `{soul, did, entries: […]}`
