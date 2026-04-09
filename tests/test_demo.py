# tests/test_demo.py — Smoke test for developer onboarding demo
# Updated: 2026-03-13 — Set SOUL_DEMO_NO_PAUSE=1 to prevent blocking on input


import pytest

from soul_protocol.demo import run_demo


@pytest.mark.asyncio
async def test_demo_runs_without_error(monkeypatch):
    """The onboarding demo should complete without raising."""
    monkeypatch.setenv("SOUL_DEMO_NO_PAUSE", "1")
    await run_demo()
