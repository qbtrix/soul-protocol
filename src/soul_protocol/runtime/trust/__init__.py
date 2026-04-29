# trust/__init__.py — Trust chain runtime package.
# Created: 2026-04-29 (#42) — Houses TrustChainManager, the runtime owner of
# a soul's TrustChain. Spec-side primitives (TrustEntry, TrustChain,
# SignatureProvider, verify_chain) live in soul_protocol.spec.trust.

from __future__ import annotations

from soul_protocol.runtime.trust.manager import TrustChainManager

__all__ = ["TrustChainManager"]
