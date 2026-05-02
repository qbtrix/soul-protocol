<!-- docs/lfdt-mentorship.md — LFDT mentorship scope, shape, and how to apply -->
<!-- Added: 2026-05-02 — Created for the LF Decentralized Trust voluntary
     track. Tracks LFDT issue #75. Names Prakash as mentor. Spells out
     the four deliverables, a suggested 12-week shape, what mentees can
     expect from review, and how to apply once LFX wires the platform. -->

# LFDT Mentorship — Soul Protocol

## About the program

Soul Protocol is part of the [Linux Foundation Decentralized Trust Mentorship Program](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/75) on the voluntary track. The program window opened on May 1, 2026. The project tracking issue is [LF-Decentralized-Trust-Mentorships/mentorship-program#75](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/75).

The mentor is Prakash (`@pocketpaw`, prakash@qbtrix.com). I maintain Soul Protocol and the related agent runtime PocketPaw, and I will be your point of contact through the program.

## What you'll work on

Four deliverables make up the technical scope:

**1. AES-256-GCM encrypted `.soul` file export and import.** The `.soul` archive currently supports password-derived encryption via scrypt; we want to harden the protocol around AEAD with explicit IV handling, associated-data binding, and round-trip tests against externally generated ciphertexts. A working export/import path that interops cleanly with future runtimes is the goal.

**2. Machine-derived key management.** Today, signing keys live next to the soul. We want a key model that survives migration between machines without leaking the private key into the shared file. This means deriving keys from a host secret, supporting key rotation, and keeping the public key embedded in the chain so verification stays simple for receivers.

**3. Digital signature verification on import.** Every `.soul` import should verify the trust chain's signatures against the embedded public key before any state is loaded. The chain primitives already exist in `spec/trust.py` and `runtime/trust/manager.py`; the import path needs to call them and refuse loads on broken chains. Read [docs/trust-chain.md](trust-chain.md) for the threat model.

**4. Cross-runtime test suite.** Souls move between runtimes. We want a fixture set plus pytest harness that round-trips a soul through PocketPaw, LangChain, and CrewAI integrations and asserts memory, identity, and chain state survive each hop without loss. This is the deliverable that turns "portable in theory" into "portable in CI."

Plus the supporting work: a clean Python SDK surface for export/import, developer documentation for each new feature, and a reflective blog post at the end of the program on the [LF Decentralized Trust blog](https://www.lfdecentralizedtrust.org/blog).

## Suggested 12-week shape

This is a shape, not a contract. We'll calibrate in week 1.

| Weeks | Focus |
|---|---|
| 1-2 | Onboarding. Read [docs/architecture.md](architecture.md), [docs/SPEC.md](SPEC.md), [docs/trust-chain.md](trust-chain.md). Run the test suite. Ship one PR against a `good first issue` to learn the review loop. |
| 3-6 | AES-256-GCM encrypted export and import, plus the machine-derived key management piece. Land each as its own PR with tests. Update the relevant docs in the same PR. |
| 7-9 | Signature verification on import. Harden the trust chain code path so import refuses broken chains. Add fixtures with deliberately tampered chains. |
| 10-12 | Cross-runtime test suite (PocketPaw, LangChain, CrewAI). Write the blog post. Final demo session. |

Most of the work happens in `runtime/crypto/`, `runtime/trust/`, `runtime/export/`, and the corresponding `tests/` paths. The `.soul` file format is documented in [docs/SPEC.md](SPEC.md).

## Skills you'll pick up

- Applied cryptography in Python (AES-GCM, Ed25519, scrypt, key derivation patterns)
- Protocol design — versioning, backward compatibility, threat modelling
- Modern Python packaging (uv, hatch, optional extras, wheel hygiene)
- Open source contribution workflow at LF scale (PR review cadence, RFC-style design notes, changelog discipline)

## What I commit to as mentor

- Async PR reviews within 48 hours on weekdays
- A weekly 30-minute sync (video or written, your call)
- Pairing on hard problems — debugging crypto round trips, designing the key derivation model, anything that gets stuck for more than a day
- Pointers to relevant prior art and people in the LF orbit when your work touches their projects

## What I'm looking for

- **PR cadence.** Roughly one substantive PR per week is a healthy rhythm. Some weeks will have two small ones, some weeks will have a single larger one. We'll talk about scope before each one.
- **Public questions.** If you're stuck for more than half a day, post in GitHub Discussions or the program channel. Other mentees benefit from the same answer.
- **A reflective blog post** at the end of the program on the LF Decentralized Trust blog. Honest and specific, not promotional.
- **A short demo session** (15-20 min) covering what shipped and one design decision you'd make differently in hindsight.

## How to apply

Applications run through the LFX Mentorship platform. The program manager Christina Harter is wiring it now; the application link will appear on the [program issue](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/75) when ready. Once it's live, this page will link directly to the LFX form.

In the meantime, scope or background questions can go to:

- [GitHub Discussions](https://github.com/qbtrix/soul-protocol/discussions) for anything public
- prakash@qbtrix.com for anything you'd rather discuss directly

A short note on your background and what draws you to portable agent identity is a good way to start.

## Why this matters

AI agents currently lose their context every time they cross runtimes. Memory, personality, and learned behavior are pinned to whatever system created them. A portable, cryptographically verifiable identity format would let agents move with their users, prove what they learned and when, and survive the runtime they were born on. That's a problem worth a few months of focused work, and it sits at a useful intersection of applied cryptography, protocol design, and AI infrastructure.
