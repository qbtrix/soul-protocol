<!-- Covers: Org management — `soul org init|status|destroy` commands, what they create,
     where the files live, and how idempotency works.
     Updated: 2026-04-14 — v0.3.1: flag list brought in line with the actually-shipped CLI
     (adds --values, --founder-name, --founder-email, --scopes, --fleet, --users-dir).
     Corrected archives-dir default to ~/.soul-archives/ (was incorrectly ~/.soul/archives/).
     Corrected destroy flags: --confirm + --i-mean-it (removed the --non-interactive --yes variant).
     Updated: feat/paw-os-init — file renamed from paw-os.md to org.md; content
     rewritten for the `soul org` CLI + `~/.soul/` default path. -->

# Org Management

A soul-protocol org is a scope-tagged append-only journal plus a root governance identity that signs the decisions a team needs to audit later. It is the container you boot a fleet of agents inside. This page covers the commands that bring an org into being, inspect it, and tear it down.

## `soul org init`

Bootstraps an empty directory into a working org. Births a governance soul, generates an Ed25519 signing key for it, opens a SQLite journal, and writes the genesis events that anchor the org timeline.

```bash
soul org init --org-name "Acme Ventures" --purpose "A software company"
```

Full form, seeding values, a founder, scopes, and a starter fleet:

```bash
soul org init \
  --org-name "Acme" \
  --purpose "AI tooling" \
  --values "audit,velocity,kindness" \
  --founder-name "Pat" --founder-email "pat@acme.com" \
  --scopes "org:sales,org:ops" \
  --fleet sales \
  --non-interactive
```

Flags:

- `--org-name TEXT` — the organization's name. Required; prompted if omitted.
- `--purpose TEXT` — optional mission statement that lands in the root soul persona.
- `--values TEXT` — comma-separated org values (3-5 recommended). Written into the root soul and emitted as a journal event.
- `--founder-name TEXT` / `--founder-email TEXT` — founder user details. When set, a user soul is created and added to the org.
- `--scopes TEXT` — comma-separated first-level scopes (e.g. `org:sales,org:ops`). Each becomes a `scope.created` event.
- `--fleet [sales|support|solo|skip]` — starter fleet to seed. `skip` creates no agents.
- `--data-dir PATH` — where to put the org. Defaults to `~/.soul/` (override with `$SOUL_DATA_DIR`).
- `--users-dir PATH` — where founder user souls live. Defaults to nesting under `--data-dir` (override with `$SOUL_USERS_DIR`).
- `--force` — overwrite an existing non-empty `--data-dir`. Without it the command refuses.
- `--non-interactive` — never prompt. Requires `--org-name` to be set.

Every step emits one or more journal events so the final org state is fully reconstructable from the event log. Re-running `init` against an initialized directory refuses unless `--force` is passed.

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
soul org status --json
```

## `soul org destroy`

Archives the org to a dated tar.gz and wipes the data-dir. Irreversible; multiple confirmations are required.

```bash
soul org destroy --confirm --i-mean-it
```

Flags:

- `--confirm` / `--i-mean-it` — both required before anything is touched.
- `--data-dir PATH` — org dir to destroy. Defaults to `~/.soul/` (override with `$SOUL_DATA_DIR`).
- `--archives-dir PATH` — where the archive lands. Defaults to `~/.soul-archives/` (a sibling of the org dir, so the archive survives the wipe). Override with `$SOUL_ARCHIVES_DIR`.
- `--non-interactive` — skip the typed-name prompt; intended for tests and scripted teardown.

In interactive mode, the CLI also asks you to type the org name at a prompt before proceeding. The destroy path writes the archive first and only then removes the data-dir. If the archive write fails, the org is left intact.

## Next

Starter fleets land today through `soul org init --fleet <sales|support|solo>`. A standalone `soul org install-fleet` that attaches a fleet to an already-initialized org is next on the roadmap — until it ships, spin up fleets by passing `--fleet` at init time, or append them by hand to `journal.db` via the Journal API. Real user invites (`soul user invite`) are a placeholder today; the full flow ships in a follow-up PR.
