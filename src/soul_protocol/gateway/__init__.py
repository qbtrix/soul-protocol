# gateway/__init__.py - REST API gateway + OpenAI-compatible LLM proxy.
# Exports: create_app(), run()
# Updated: 2026-11-14 — run() passes the loaded soul's path to create_app so
#   consent revokes and consented reads/writes are saved to disk.

import asyncio
import os
from pathlib import Path

from soul_protocol.gateway.app import create_app

__all__ = ["create_app", "run"]


def _resolve_soul_path(path: str | None, directory: str | None) -> str:
    if path:
        return path
    if not directory:
        raise RuntimeError("Set SOUL_PATH (or SOUL_DIR) to run soul-api")
    root = Path(directory)
    if not root.is_dir():
        raise RuntimeError(f"SOUL_DIR is not a directory: {directory}")
    candidates = sorted(
        p
        for p in root.iterdir()
        if p.suffix == ".soul" or (p.is_dir() and (p / "soul.json").exists())
    )
    if not candidates:
        raise RuntimeError(f"No souls found in SOUL_DIR: {directory}")
    return str(candidates[0])


def run(
    host: str = "127.0.0.1",
    port: int = 8000,
    soul_path: str | None = None,
    soul_dir: str | None = None,
) -> None:
    """Start the gateway + LLM proxy (uvicorn).

    Loads a soul from ``SOUL_PATH`` (single file) or ``SOUL_DIR`` (first soul
    found), builds the app via :func:`create_app`, and serves it on
    ``host:port``. Upstream LLM is configured via ``SOUL_LLM_BASE_URL`` /
    ``SOUL_LLM_API_KEY`` / ``SOUL_LLM_MODEL``.
    """
    import uvicorn

    from soul_protocol.runtime.soul import Soul

    path = _resolve_soul_path(
        soul_path or os.environ.get("SOUL_PATH"),
        soul_dir or os.environ.get("SOUL_DIR"),
    )
    soul = asyncio.run(Soul.awaken(path))
    uvicorn.run(create_app(soul, soul_path=path), host=host, port=port)
