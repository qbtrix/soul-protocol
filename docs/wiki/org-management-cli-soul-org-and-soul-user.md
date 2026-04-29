---
{
  "title": "Org Management CLI — `soul org` and `soul user`",
  "summary": "Implements the `soul org init`, `soul org status`, `soul org destroy`, and `soul user invite` commands for managing multi-soul organisational deployments. Creates a governance root soul, writes journal events for every lifecycle action, and enforces layered protections against root-soul deletion.",
  "concepts": [
    "org management",
    "governance soul",
    "Root soul",
    "soul org init",
    "soul org destroy",
    "append-only journal",
    "PII protection",
    "multi-soul deployment",
    "SOUL_DATA_DIR",
    "root-soul protection",
    "soul user invite",
    "scope tree",
    "SQLite journal"
  ],
  "categories": [
    "cli",
    "org-layer",
    "security"
  ],
  "source_docs": [
    "b80bd12b91103e8f"
  ],
  "backlinks": null,
  "word_count": 499,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`cli/org.py` handles the organisation layer of soul-protocol — the ability to run multiple souls under a shared governance identity within a single deployment. It was originally `cli/paw_os.py` and has been progressively extended from a minimal bootstrap into a full 8-step onboarding wizard.

## Org Architecture

An org deployment consists of:

```
~/.soul/   (default, overridable via SOUL_DATA_DIR)
├── journal.db          ← append-only SQLite event log
├── souls/              ← individual soul directories
│   ├── root/           ← governance soul (Root)
│   └── <founder>/      ← founder user soul
└── archives/           ← tarballs from org destroy
```

The **governance soul** (`Root`) is the cryptographic and policy anchor. It:
- Holds the signing key
- Authors `scope.created` events
- Approves admin grants
- Has an OCEAN profile tuned for high conscientiousness and minimal extraversion (0.1) — it exists to audit, not to chat

## `soul org init` — 8-Step Wizard

1. Check that `data_dir` is empty (prevent double-init)
2. Create directory structure
3. Open the journal and write `org.created` event
4. Collect org name, purpose, and values from the user
5. Birth the governance soul (`Root`) with fixed OCEAN profile
6. Prompt for founder name/email, birth the founder user soul
7. Write `user.joined` event (email intentionally excluded — see PII note)
8. Write the first-level scope tree and display the starter fleet hint

### PII Design Decision

Founder email is collected for the onboarding flow but is **not** written to the journal. The journal is append-only with no right-to-erasure path; storing PII there would permanently violate GDPR. Email stays in the founder's soul file, which supports deletion via `soul delete`.

## `soul org status`

Reads the journal directly and projects current state: org name, created timestamp, member count, recent events. This is a read-only operation — no soul awakening required.

## `soul org destroy`

Tarballs the entire org directory under `archives/` before wiping it. A critical bug fix (2026 onboarding-full branch) ensures the tarball writer **excludes** `archives_dir` from the source tree — without this exclusion, `tarfile` would try to read the partially-written tarball as a source file, raising `ReadError` and leaving the org neither archived nor deleted.

## Root-Soul Protection (Three Layers)

1. **Runtime layer**: `Soul.role = "root"` prevents `Soul.delete()` from completing
2. **Journal layer**: `root_agent` flag blocks certain state transitions
3. **CLI layer**: `soul delete` in `main.py` checks role before proceeding

## Key Constants

| Constant | Value / Role |
|----------|-------------|
| `GOVERNANCE_PERSONA_NAME` | `"Root"` |
| `GOVERNANCE_OCEAN` | conscientiousness=0.95, extraversion=0.1 |
| `GOVERNANCE_VALUES` | audit, durability, minimal surface, verifiable |
| `VALID_FLEETS` | permitted deployment fleet types |

## Known Gaps

- `user_invite()` is a **placeholder** stub that prints a message and exits. The real invite flow (email sending, token generation, onboarding link) is deferred to a follow-up PR.
- The scope tree created during `org init` is a starter skeleton; dynamic scope management (add/remove scopes, assign souls to scopes) has no CLI yet.
- TODO comment in source: `load_template("governance")` should replace the hardcoded `GOVERNANCE_PERSONA_*` constants once the template API lands.
