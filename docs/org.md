<!-- Covers: Org management — `soul org init|status|destroy` commands, what they create,
     where the files live, and how idempotency works.
     Updated: feat/paw-os-init — file renamed from paw-os.md to org.md; content
     rewritten for the `soul org` CLI + `~/.soul/` default path. Add an `install-fleet`
     stub under Next so readers know the fleet command is coming without pretending it
     already exists. -->

# Org Management

A soul-protocol org is a scope-tagged append-only journal plus a root governance identity that signs the decisions a team needs to audit later. It is the container you boot a fleet of agents inside. This page covers the commands that bring an org into being, inspect it, and tear it down.

## `soul org init`

Bootstraps an empty directory into a working org. Births a governance soul, generates an Ed25519 signing key for it, opens a SQLite journal, and writes the genesis events that anchor the org timeline.

```bash
soul org init --org-name "Acme Ventures" --purpose "A software company"
```

Flags:

- `--org-name TEXT` — the organization's name. Required; prompted if omitted.
- `--purpose TEXT` — optional mission statement that lands in the root soul persona.
- `--data-dir PATH` — where to put the org. Defaults to `~/.soul/` (override with `$SOUL_DATA_DIR`).
- `--force` — overwrite an existing non-empty `--data-dir`. Without it the command refuses.
- `--non-interactive` — never prompt. Requires `--org-name` to be set.

Re-running `init` against an initialized directory is a no-op unless `--force` is passed. The command is idempotent by design so a half-finished setup can be re-run safely.

## What gets created

Under `~/.soul/` (or your `--data-dir`):

```
~/.soul/
├── root.soul              # Governance soul, zip-packed
├── journal.db             # SQLite WAL journal, two genesis events in it
└── keys/
    ├── root.ed25519       # Private signing key, chmod 0600
    ├── root.ed25519.pub   # Public key, raw Ed25519 bytes
    └── root.did           # Root DID string
```

The journal starts with two events:

1. `org.created` — carries the org name, purpose, and the OS user that ran the command.
2. `scope.created` for `org:*` — the top-level scope everything else writes under, caused by the `org.created` event (see `causation_id`).

The root soul has OCEAN traits weighted toward conscientiousness and low extraversion. It is designed to sign things, not to chat.

## `soul org status`

Prints a human-readable summary of an initialized org: DID, journal head, event count, data-dir location, whether the root soul is sealed. Read-only and safe to run against a live org.

```bash
soul org status
soul org status --data-dir /path/to/org
```

## `soul org destroy`

Archives the org to a dated tar.gz and wipes the data-dir. Irreversible; multiple confirmations are required.

```bash
soul org destroy --confirm --i-mean-it
```

Flags:

- `--confirm` / `--i-mean-it` — both required before anything is touched.
- `--archives-dir PATH` — where the archive lands. Defaults to `<data-dir>/archives/`.
- `--non-interactive --yes` — skip the interactive prompts; intended for tests and scripted teardown.

The destroy path writes the archive first and only then removes the data-dir. If the archive write fails, the org is left intact.

## Next

The fleet install (`soul org install-fleet <template>`) is the next step on the roadmap: it spawns a starter team attached to an initialized org. It is not yet implemented — until it ships, the org is ready to accept journal appends from whatever tooling you point at `journal.db`.
