# gateway/__init__.py - REST API gateway + OpenAI-compatible LLM proxy.
# Exports: create_app(), run()

import asyncio
import os
from pathlib import Path

from soul_protocol.gateway.app import create_app

__all__ = ["create_app", "run"]


def _load_soul(path: str | None, directory: str | None):
    from soul_protocol.runtime.soul import Soul

    if path:
        return asyncio.run(Soul.awaken(path))
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
    return asyncio.run(Soul.awaken(str(candidates[0])))


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

    soul = _load_soul(
        soul_path or os.environ.get("SOUL_PATH"),
        soul_dir or os.environ.get("SOUL_DIR"),
    )
    uvicorn.run(create_app(soul), host=host, port=port)
