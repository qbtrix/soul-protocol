# Consent Passes

A consent pass lets one app use some of a soul's memory domains for a limited time. While the pass is active, the app can only reach the domains it lists. Every grant, read, write and refusal is signed onto the soul's [trust chain](trust-chain.md).

## Example

The soul keeps memories in domains such as `health`, `finance` and `work`. A fitness app should see `health` and nothing else, for one week.

```bash
soul consent grant .soul/ --app fitness-app --domain health --for 7d
```

This prints a pass id (`cp_...`) and a token (`scp_...`). Give the token to the app. Only a hash of the token is stored, so it cannot be shown again. If it is lost, revoke the pass and grant a new one.

The app sends the token with each request:

```bash
curl -X POST http://127.0.0.1:8000/recall \
  -H "Content-Type: application/json" \
  -H "X-Consent-Token: scp_..." \
  -d '{"query": "injuries"}'
```

- A request for `health` memories returns them.
- A request with `"domain": "finance"` returns `403` with `"reason": "domain_not_allowed"`.
- After 7 days, or after `soul consent revoke .soul/ cp_...`, requests return `403` with `expired` or `revoked`.

To see what happened:

```bash
soul consent log .soul/ --verify
```

## What a pass checks

The pass is checked again on every call, so a revoke or expiry takes effect on the app's next request. A request is refused when:

| Reason | Meaning |
|---|---|
| `unknown_token` | No pass has this token. |
| `revoked` | The owner revoked the pass. |
| `expired` | The pass's time is up. |
| `invalid_signature` | The stored pass was changed after it was signed, or it was issued by another soul. |
| `domain_not_allowed` | The request named a domain that is not in the pass. |
| `write_not_allowed` | The pass is read-only. |
| `audit_unavailable` | The soul was loaded without its private key, so the access could not be signed. |

Refusals for a real pass are logged as `consent.denied`. Requests with an unknown token are only counted (`unknown_token_denials` in the consent file). Anyone can send a random token, and signing those requests would let them grow the chain and push real events out of the log.

Even inside an allowed domain:

- **PRIVATE memories are never returned to an app.** BONDED and PUBLIC memories are returned, because the pass is the owner's explicit permission.
- **Writes need a `read_write` pass** (`--access read-write`), and go into one of the pass's domains.

## The audit trail

Each event is appended to the trust chain as `consent.grant`, `consent.revoke`, `consent.read`, `consent.write` or `consent.denied`. A read entry records which memory ids were returned.

The trust chain stores only a hash of each event. The readable details are kept in `consent/consent.json`, which holds the newest 1,000 events. `soul consent log --verify` (or `Soul.verify_consent_log()`) checks two things:

- **Each log line matches a signed chain entry.** An edited line no longer matches.
- **Each signed `consent.*` entry is still in the log.** A deleted line shows up as missing. Lines dropped by the 1,000-event limit are tracked and not reported.

A line can also show as unverified if it was never signed (revokes and denials on a soul without its private key) or if the chain was later pruned (`trust_chain_max_entries`).

The pass checks and this verification make tampering visible, but they are a safety net, not a wall. The soul's private key is stored next to `consent.json` (`keys/private.key`). Anyone who can edit the soul's files can read that key and sign whatever they like. Protect the soul's folder like any other secret, and use [encryption](encryption.md) for files that leave your machine.

## Interfaces

| Task | CLI | MCP | Python |
|---|---|---|---|
| Grant | `soul consent grant PATH --app A --domain D [--for 7d] [--access read-write]` | `soul_consent_grant` | `soul.grant_consent(app, domains, duration="7d")` |
| List | `soul consent list PATH [--all]` | `soul_consent_list` | `soul.consent_passes()` |
| Revoke | `soul consent revoke PATH PASS_ID` | `soul_consent_revoke` | `soul.revoke_consent(pass_id)` |
| Log | `soul consent log PATH [--verify]` | `soul_consent_log` | `soul.consent_events()`, `soul.verify_consent_log()` |
| App read | `X-Consent-Token` on `POST /recall` | `soul_recall(consent_token=...)` | `soul.consent_session(token).recall(query)` |
| App write | `X-Consent-Token` on `POST /remember` | `soul_remember(consent_token=...)` | `soul.consent_session(token).remember(content)` |

`soul_consent_grant` returns the token in its output, so it ends up in the agent's transcript. Use `soul consent grant` on the CLI when the agent should not see the token.

The dashboard (`soul-api`, then open `/dashboard`) has a **Consents** section. It lists passes with their status and a Revoke button, shows the access log, and shows whether the log matches the chain. Passes are granted from the CLI, MCP or Python, not from the dashboard, because the gateway has no login of its own.

Durations are a number plus `m`, `h`, `d` or `w`, up to 365 days.

## Limits

Consent passes control access through the soul's own interfaces: the Python `ConsentSession`, the MCP `consent_token`, and the gateway header. They are not encryption.

- **Requests without a token still work as before.** Apps that call `/recall` or `soul_recall` without a token get the normal, unrestricted view. Passes protect the memory only when untrusted apps are given a token instead of direct access.
- **Anyone who can read the soul's files can read its memories.** Use [encryption](encryption.md) for data at rest.
- **The gateway has no authentication.** It binds to `127.0.0.1`. Revoking from the dashboard is allowed, because revoking only removes access.
