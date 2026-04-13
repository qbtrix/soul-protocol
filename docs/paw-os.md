<!-- Covers: Paw OS onboarding — `soul paw os init` command, what it creates, what to do next.
     Created: feat/paw-os-init — Workstream A slice 3 of the Org Architecture RFC (#164). -->

# Paw OS

A Paw OS org is a scope-tagged, append-only journal plus a root governance identity that signs the decisions a team needs to audit later. It is the container you boot a fleet of agents inside. This page covers the one command that brings a brand-new org into being.

## `soul paw os init`

Bootstraps an empty directory into a working Paw OS instance. It births a governance soul, generates an Ed25519 signing key for it, opens a SQLite journal, and writes the genesis events that anchor the org timeline.

```bash
soul paw os init --org-name "Acme Ventures" --purpose "A software company"
```

Flags:

- `--org-name TEXT` — the organization's name. Required; prompted if omitted.
- `--purpose TEXT` — optional mission statement that lands in the root soul persona.
- `--data-dir PATH` — where to put the org. Defaults to `~/.pocketpaw/org/`.
- `--force` — overwrite an existing non-empty `--data-dir`. Without this the command refuses.
- `--non-interactive` — never prompt. Requires `--org-name` to be set.

## What gets created

Under `~/.pocketpaw/org/` (or your `--data-dir`):

```
~/.pocketpaw/org/
├── root.soul              # Governance soul, zip-packed
├── journal.db             # SQLite WAL journal, two genesis events in it
└── keys/
    ├── root.ed25519       # Private signing key, chmod 0600
    ├── root.ed25519.pub   # Public key, raw Ed25519 bytes
    └── root.did           # Root DID string
```

The journal starts with two events:

1. `org.created` — carries the org name, purpose, and the OS user that ran the command.
2. `scope.created` for `org:*` — the top-level scope everything else writes under. It is caused by the `org.created` event (see `causation_id`).

The root soul has OCEAN traits heavily weighted toward conscientiousness and low extraversion. It is designed to sign things, not to chat.

## Next

The starter-fleet install (`soul paw os fleet install`) lands in Workstream B and will spawn the first agent team attached to your org. Until then the org is ready to accept journal appends from whatever tooling you point at `journal.db`.
