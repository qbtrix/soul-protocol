# eternal/manager.py — Multi-tier eternal storage manager.
# Created: 2026-03-06 — Manages registration, archiving, recovery,
#   and verification across multiple EternalStorageProvider backends.
# Updated: 2026-03-29 — Added with_mocks() classmethod factory for convenience.

from __future__ import annotations

from typing import Any

from .protocol import ArchiveResult, EternalStorageProvider, RecoverySource


class EternalStorageManager:
    """Manages multi-tier eternal storage for souls.

    Register one or more EternalStorageProvider instances, then use
    archive/recover/verify_all to interact with them uniformly.
    """

    def __init__(self) -> None:
        self._providers: dict[str, EternalStorageProvider] = {}
        # Track archives: soul_id -> list of RecoverySource
        self._archives: dict[str, list[RecoverySource]] = {}

    @classmethod
    def with_mocks(cls) -> EternalStorageManager:
        """Create an EternalStorageManager with all mock providers registered."""
        from .providers.mock_arweave import MockArweaveProvider
        from .providers.mock_ipfs import MockIPFSProvider

        mgr = cls()
        mgr.register(MockIPFSProvider())
        mgr.register(MockArweaveProvider())
        return mgr

    @property
    def providers(self) -> dict[str, EternalStorageProvider]:
        """Return registered providers."""
        return dict(self._providers)

    def register(self, provider: EternalStorageProvider) -> None:
        """Register a storage provider by its tier name."""
        self._providers[provider.tier_name] = provider

    def unregister(self, tier_name: str) -> bool:
        """Unregister a provider. Returns True if it was registered."""
        return self._providers.pop(tier_name, None) is not None

    async def archive(
        self,
        soul_data: bytes,
        soul_id: str,
        tiers: list[str] | None = None,
        **kwargs: Any,
    ) -> list[ArchiveResult]:
        """Archive to one or more tiers. Returns list of results.

        If tiers is None, archives to all registered providers.
        Raises ValueError if a requested tier is not registered.
        """
        target_tiers = tiers or list(self._providers.keys())
        results: list[ArchiveResult] = []

        for tier in target_tiers:
            provider = self._providers.get(tier)
            if provider is None:
                raise ValueError(
                    f"No provider registered for tier '{tier}'. "
                    f"Available: {list(self._providers.keys())}"
                )

            result = await provider.archive(soul_data, soul_id, **kwargs)
            results.append(result)

            # Track this archive as a recovery source
            source = RecoverySource(
                tier=tier,
                reference=result.reference,
                available=True,
            )
            self._archives.setdefault(soul_id, []).append(source)

        return results

    async def recover(self, sources: list[RecoverySource]) -> bytes:
        """Try to recover soul data from sources in order.

        Iterates through sources, attempting retrieval from the matching
        provider. Returns the first successful result.

        Raises:
            ValueError: If no provider is registered for a source's tier.
            RuntimeError: If all sources fail.
        """
        errors: list[str] = []

        for source in sources:
            provider = self._providers.get(source.tier)
            if provider is None:
                errors.append(f"{source.tier}: no provider registered")
                continue

            if not source.available:
                errors.append(f"{source.tier}: source marked unavailable")
                continue

            try:
                data = await provider.retrieve(source.reference)
                return data
            except Exception as exc:
                errors.append(f"{source.tier}: {exc}")
                continue

        raise RuntimeError(f"Failed to recover from any source. Errors: {'; '.join(errors)}")

    async def get_recovery_sources(self, soul_id: str) -> list[RecoverySource]:
        """Get all tracked recovery sources for a soul."""
        return list(self._archives.get(soul_id, []))

    async def verify_all(self, soul_id: str) -> dict[str, bool]:
        """Verify all archives for a soul across registered providers.

        Returns a dict mapping tier name to verification status.
        """
        sources = self._archives.get(soul_id, [])
        results: dict[str, bool] = {}

        for source in sources:
            provider = self._providers.get(source.tier)
            if provider is None:
                results[source.tier] = False
                continue

            try:
                ok = await provider.verify(source.reference)
                results[source.tier] = ok
                source.available = ok
            except Exception:
                results[source.tier] = False
                source.available = False

        return results
