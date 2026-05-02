<!-- CONTRIBUTING.md — soul-protocol contributor guide -->
<!-- Added: 2026-05-02 — Initial contributor guide written for the LFDT
     mentorship program window. Points at existing docs rather than
     duplicating them, names the mentor (Prakash), and sets expectations
     on PR style (Conventional Commits, target dev, one concern per PR).
     Updated: 2026-05-02 — humanizer pass: dropped two rule-of-three
     phrases (opening sentence and Code of Conduct line) per the
     workspace /humanize gate. -->

# Contributing to Soul Protocol

Soul Protocol is an open standard plus a Python reference runtime for portable AI agent identity and memory. This guide is for anyone sending a PR or filing an issue. If you're applying for the LFDT mentorship program, also read [docs/lfdt-mentorship.md](docs/lfdt-mentorship.md) — it covers the mentee scope.

## Quick start

The full setup walkthrough lives in [docs/getting-started.md](docs/getting-started.md). The short version:

```bash
git clone https://github.com/qbtrix/soul-protocol.git
cd soul-protocol
uv sync
uv run pytest tests/
```

If `uv sync` finishes and the test suite is green, you're good to go. The repo uses [uv](https://github.com/astral-sh/uv), not pip, for development. Python 3.11 or newer.

## Codebase orientation

The reference implementation lives in `src/soul_protocol/`:

- `spec/` — language-agnostic protocol types. Pydantic models for identity, memory, the `.soul` container, journal, decisions, retrieval. No I/O, no opinions. Anything that ships in `.soul` files is defined here.
- `runtime/` — the Python reference runtime. Memory tiers (`memory/`), psychology pipeline (`cognitive/`), trust chain (`trust/`), Ed25519 signing (`crypto/`), `.soul` export/import (`export/`). Opinionated, batteries-included.
- `engine/` — org-layer engine. SQLite WAL journal and credential broker.
- `cli/` — Click entry points (`soul`, `soul org`, `soul template`, etc.).
- `mcp/` — MCP server (24 tools, 3 resources).

Architecture diagrams and module dependencies are in [docs/architecture.md](docs/architecture.md). The language-agnostic contract is in [docs/SPEC.md](docs/SPEC.md). Read those before any structural change.

## Running tests

```bash
uv run pytest tests/
```

Tests use `pytest-asyncio` for async coroutines. New features should land with tests. Bug fixes should land with a failing test that your fix turns green.

## Submitting a PR

A few conventions to keep merges clean:

- **Branch off `dev`**, not `main`. PRs target `dev`. Releases roll up from `dev` to `main`.
- **One concern per PR.** A bug fix and an unrelated refactor go in two PRs.
- **Conventional Commits** in the PR title: `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`. Examples: `feat(trust): rotate signing keys`, `fix(memory): prevent duplicate seq on observe race`.
- **Tests required** for new features. Bug fixes need a regression test.
- **Lint clean.** `uv run ruff check .` and `uv run ruff format --check .` should both pass.
- The PR template asks for a 2-3 sentence summary, how to test, and a checklist. Fill them out — it makes review faster.

## Code style

Ruff handles formatting and linting. Config is in `pyproject.toml`. Run `uv run ruff format .` before pushing.

## Finding a first issue

Issues tagged [`good first issue`](https://github.com/qbtrix/soul-protocol/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) are scoped, well-described, and a good entry point. They tend to live in `runtime/trust/`, `runtime/export/`, and the docs. If you want to chat about scope before opening a PR, GitHub Discussions is the right place.

## Reporting bugs

File an issue using the bug report template. The template asks for `soul --version`, your Python version, OS, repro steps, and expected vs actual behavior. Templates live under `.github/ISSUE_TEMPLATE/`.

For security issues, please email prakash@qbtrix.com instead of opening a public issue.

## LFDT Mentorship

Soul Protocol joined the [Linux Foundation Decentralized Trust Mentorship Program](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/75) in May 2026. Prakash (`@pocketpaw`, prakash@qbtrix.com) is the mentor. The full mentee scope, suggested 12-week shape, and how to apply are in [docs/lfdt-mentorship.md](docs/lfdt-mentorship.md). Mentee applicants should read that doc first.

## Scope

Things this repo accepts:

- New memory tiers, layers, or query strategies that fit the existing protocol
- Extensions to the `.soul` file format (versioned, backward-compatible)
- Runtime adapters (cognitive engines, embedding providers, eternal storage backends)
- Cross-language schema work and reference test vectors
- Documentation, examples, tutorials, fixtures
- Bug fixes and test coverage

Out of scope:

- Provider-specific glue that doesn't generalize (e.g., a single proprietary platform's wire format)
- UI work — soul-protocol is CLI plus library. Frontend belongs in consuming projects like PocketPaw.
- Anything that imports from a consumer project. The reverse dependency direction is what makes the protocol portable.

If you're unsure, open a Discussion before writing code.

## Code of Conduct

This project follows the [Linux Foundation Code of Conduct](https://lfprojects.org/policies/code-of-conduct/). Maintainers may remove comments or contributors that violate it.
