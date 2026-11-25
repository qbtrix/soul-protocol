# Consent Passes

A consent pass lets one app use some of a soul's memory domains for a limited time. While the pass is active, the app can only reach the domains it lists. Every grant, read, write and refusal is signed onto the soul's [trust chain](trust-chain.md).

This page covers the runtime API and the `soul consent` CLI. MCP tools and the gateway's `X-Consent-Token` header are planned as a follow-up.

## Example

The soul keeps memories in domains such as `health`, `finance` and `work`. A fitness app should see `health` and nothing else, for one week.

```bash
soul consent grant .soul/ --app fitness-app --domain health --for 7d
```

This prints a pass id (`cp_...`) and a token (`scp_...`). Give the token to the app. Only a hash of the token is stored, so it cannot be shown again. If it is lost, revoke the pass and grant a new one.

The app uses the token through a session:

```python
session = soul.consent.session(token)
memories = await session.recall("injuries")            # health memories only
await session.recall("salary", domain="finance")       # raises ConsentDeniedError: domain_not_allowed
```

After 7 days, or after `soul consent revoke .soul/ cp_...`, every call raises `ConsentDeniedError` with reason `expired` or `revoked`.

To see what happened:

```bash
soul consent log .soul/ --verify
```

## What a pass checks

The pass is checked again on every call (and once more after the call finishes), so a revoke or expiry takes effect on the app's next request. A request is refused when:

| Reason | Meaning |
|---|---|
| `unknown_token` | No pass has this token. |
| `revoked` | The owner revoked the pass. Checked against the signed `consent.revoke` chain entry as well as the consent file, so editing the file does not un-revoke a pass. |
| `expired` | The pass's time is up. |
| `invalid_signature` | The pass was changed after it was signed, was issued by another soul, or was signed by a key the soul no longer uses (rotating the key invalidates outstanding passes). |
| `domain_not_allowed` | The request named a domain that is not in the pass. |
| `write_not_allowed` | The pass is read-only. |
| `audit_unavailable` | The soul was loaded without its private key, so the access could not be signed. |

Even inside an allowed domain:

- **PRIVATE memories are never returned to an app.** BONDED and PUBLIC memories are returned, because the pass is the owner's explicit permission.
- **Writes need a `read_write` pass** (`--access read-write`) and go into one of the pass's domains. Only semantic, episodic and procedural memories can be written. App writes are stored with `provenance=agent` and `source="app:<app_id>"`.
- **A write that can't be audited is undone** (purged, with a `memory.purge` chain entry), whatever the error.

## The audit trail

Each event is appended to the trust chain as `consent.grant`, `consent.revoke`, `consent.read`, `consent.write`, `consent.denied` or `consent.trim`. A read entry records which memory ids were returned. See [Consent actions](trust-chain.md#consent-actions) for the payloads.

The chain stores only a hash of each event. The readable details are kept in `consent/consent.json`. `soul consent log --verify` (or `soul.consent.verify()`) checks two things:

- **Each log line matches the signed chain entry it points at.** An edited line no longer matches.
- **Each signed `consent.*` entry is still in the log, or listed in a signed trim record.** A deleted line shows up as missing.

To keep the log from being flooded:

- **Unknown tokens are counted, not logged.** Anyone can send a random token, so these requests never touch the chain or the log, and never create a consent file on their own.
- **Repeated refusals are folded.** For a given pass and reason, one line is logged (and signed) per hour; the line's `count` says how many refusals it stands for. A revoked or expired token hammered 1,000 times adds one line.
- **Grant and revoke lines are never trimmed.** When reads, writes and refusals pass 1,000 lines, the oldest are dropped in a batch, and a signed `consent.trim` entry lists exactly which ones.
- **Long-ended passes are removed** 90 days after they expire or are revoked.

If the chain itself is pruned (`trust_chain_max_entries`), log lines that point at removed entries are reported as `pruned`, not as failures.

These checks make tampering visible, but they are a safety net, not a wall. The soul's private key is stored next to `consent.json` (`keys/private.key`). Anyone who can edit the soul's files can read that key and sign whatever they like. Protect the soul's folder like any other secret, and use [encryption](encryption.md) for files that leave your machine.

## Interfaces

| Task | CLI | Python |
|---|---|---|
| Grant | `soul consent grant PATH --app A --domain D [--for 7d] [--access read-write]` | `soul.consent.grant(app, domains, duration="7d")` |
| List | `soul consent list PATH [--all]` | `soul.consent.passes()` |
| Revoke | `soul consent revoke PATH PASS_ID` | `soul.consent.revoke(pass_id)` |
| Log | `soul consent log PATH [--verify]` | `soul.consent.events()`, `soul.consent.verify()` |
| App read | | `soul.consent.session(token).recall(query)` |
| App write | | `soul.consent.session(token).remember(content)` |

All CLI commands take `--password` for encrypted `.soul` files. Durations are a number plus `m`, `h`, `d` or `w`, up to 365 days.

## Signing keys and `.soul` files

Granting a pass, and serving consented reads and writes, needs the soul's private key. The CLI keeps it when it saves, the same as the other `soul` commands. A `.soul` file exported with the default `include_keys=False` has no private key, so it can only list and revoke passes: grants fail, and consented reads and writes are refused with `audit_unavailable`.

## Limits

Consent passes control access through `ConsentSession`. They are advisory: they are not encryption, and they don't restrict code that holds the `Soul` object directly.

- **Calls without a token are unrestricted, as before.** `soul.recall(...)` still sees everything. Passes protect the memory only when an app is given a token instead of the soul itself.
- **Anyone who can read the soul's files can read its memories.** Use [encryption](encryption.md) for data at rest.

An opt-in strict mode, where token-less calls through MCP and the gateway are refused, is proposed as a follow-up.
