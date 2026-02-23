# dashboard/app.py — Local web dashboard server for Soul Protocol
# Created: v0.3.0 — Uses stdlib http.server for zero deps. Serves HTML + JSON API.
#   Loads soul data from .soul files, .soul/ directories, or any dir with soul.json.
#   Routes: GET / (index.html), GET /api/soul (full soul JSON).

from __future__ import annotations

import asyncio
import http.server
import json
import webbrowser
from pathlib import Path
from typing import Any


def _load_soul_data(path: str) -> dict[str, Any]:
    """Load soul data from various source formats and build API payload."""
    p = Path(path).resolve()

    if p.suffix == ".soul" and p.is_file():
        # .soul ZIP archive
        from soul_protocol.export.unpack import unpack_soul

        data = p.read_bytes()
        config, memory_data = asyncio.run(unpack_soul(data))
    elif p.is_dir():
        # Directory with soul.json (e.g. .soul/ folder)
        from soul_protocol.storage.file import load_soul_full

        config, memory_data = asyncio.run(load_soul_full(p))
        if config is None:
            raise FileNotFoundError(f"No soul.json in {p}")
    else:
        raise ValueError(f"Unsupported soul path: {path}")

    # Build the data structure for the frontend
    identity = config.identity
    state = config.state
    dna = config.dna
    core_mem = config.core_memory

    # Memory tier lists
    episodic = memory_data.get("episodic", [])
    semantic = memory_data.get("semantic", [])
    procedural = memory_data.get("procedural", [])
    graph = memory_data.get("graph", {})
    self_model = memory_data.get("self_model", {})

    return {
        "identity": {
            "name": identity.name,
            "did": identity.did,
            "archetype": identity.archetype,
            "born": identity.born.isoformat() if identity.born else None,
            "core_values": identity.core_values,
            "origin_story": identity.origin_story,
            "bonded_to": identity.bonded_to,
        },
        "state": {
            "mood": state.mood.value if hasattr(state.mood, "value") else str(state.mood),
            "energy": state.energy,
            "focus": state.focus,
            "social_battery": state.social_battery,
        },
        "dna": {
            "personality": {
                "openness": dna.personality.openness,
                "conscientiousness": dna.personality.conscientiousness,
                "extraversion": dna.personality.extraversion,
                "agreeableness": dna.personality.agreeableness,
                "neuroticism": dna.personality.neuroticism,
            },
            "communication": {
                "warmth": dna.communication.warmth,
                "verbosity": dna.communication.verbosity,
                "humor_style": dna.communication.humor_style,
                "emoji_usage": dna.communication.emoji_usage,
            },
        },
        "core_memory": {
            "persona": core_mem.persona if core_mem else "",
            "human": core_mem.human if core_mem else "",
        },
        "memories": {
            "episodic": episodic,
            "semantic": semantic,
            "procedural": procedural,
        },
        "graph": graph,
        "self_model": self_model,
        "lifecycle": config.lifecycle.value if hasattr(config.lifecycle, "value") else str(config.lifecycle),
        "stats": {
            "episodic_count": len(episodic),
            "semantic_count": len(semantic),
            "procedural_count": len(procedural),
            "entity_count": len(graph.get("entities", {})) if isinstance(graph, dict) else 0,
            "total_memories": len(episodic) + len(semantic) + len(procedural),
        },
    }


def _get_template() -> str:
    """Load the dashboard HTML template via importlib.resources."""
    import importlib.resources as resources

    ref = resources.files("soul_protocol.dashboard.templates").joinpath("index.html")
    return ref.read_text(encoding="utf-8")


class _Handler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the Soul dashboard."""

    soul_data: dict = {}
    template: str = ""

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/api/soul" or self.path.startswith("/api/soul?"):
            self._serve_soul()
        else:
            self.send_error(404)

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.template.encode("utf-8"))

    def _serve_soul(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(self.soul_data, default=str).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress noisy request logs


def start_dashboard(
    path: str = ".soul",
    port: int = 5678,
    open_browser: bool = True,
) -> None:
    """Start the Soul dashboard server.

    Args:
        path: Path to .soul file, .soul/ directory, or directory with soul.json.
        port: HTTP port (default 5678).
        open_browser: Whether to auto-open in browser.
    """
    import sys

    print(f"Loading soul from {path}...")
    try:
        _Handler.soul_data = _load_soul_data(path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    _Handler.template = _get_template()

    name = _Handler.soul_data.get("identity", {}).get("name", "Unknown")
    print(f"Soul: {name}")
    print(f"Dashboard: http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    server = http.server.HTTPServer(("localhost", port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.shutdown()
