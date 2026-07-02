# server.py — "The Butcher Remembers": stdlib-only demo server that renders the
#   scripted grudge arc in a browser.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Serves the 2D canvas
#   client (index.html / app.js / style.css, same folder) and bridges HTTP onto
#   the Game Profile's GameWorld. Stdlib only: http.server.ThreadingHTTPServer +
#   json + urllib.parse — no frameworks, no build step, no npm.
#
#   Async bridge: GrudgeKernel/GameWorld APIs are async, HTTP handlers are
#   threads. ONE background thread runs ONE asyncio event loop forever; every
#   handler marshals its coroutine onto it via asyncio.run_coroutine_threadsafe
#   and blocks on the result. That serializes all world mutation on one loop —
#   no per-request loops, no locks.
#
#   Endpoints:
#     GET  /            -> index.html (plus /app.js, /style.css — whitelisted)
#     GET  /snapshot    -> GameWorld.snapshot() (zones, phase, per-NPC HUD state)
#     GET  /events?since=N -> world events with t > N (poll cursor)
#     POST /line {player, text, kind?, npc?} -> world.beat(...) summary
#     POST /reset       -> rebuild the world fresh, return its snapshot
#
#   World: Bjorn (butcher, stall) + Astrid (innkeeper, tables) as GrudgeKernels,
#   Ragnar as the PlayerSoul (door). TemplatedDialogueEngine by DEFAULT —
#   deterministic and free; the LLM switch is BD-2's job. --scripted auto-plays
#   the canonical arc (greet -> trade -> betrayal -> theft -> Astrid control ->
#   return to Bjorn, who remembers) with a short delay between beats.
#
# Run:  uv run python examples/butcher_remembers/server.py --scripted
# Then: open http://localhost:8777

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from soul_protocol.profiles.game import GameWorld, GrudgeKernel, PlayerSoul

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8777

# Static whitelist: path -> (filename in this folder, content type). Nothing
# else on disk is reachable — no directory traversal surface.
STATIC: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}

ASTRID_PERSONA = (
    "I am Astrid, the sharp-eyed innkeeper. I pour honest ale, keep clean rooms, "
    "and miss nothing that happens under my roof."
)

# The canonical scripted arc: (npc, kind, player line). Greet -> trade ->
# betrayal -> theft -> Astrid control beat -> back to Bjorn, who remembers.
SCRIPT: list[tuple[str, str, str]] = [
    ("Bjorn", "neutral", "Good morning, Bjorn! Fine sausages you have today."),
    ("Bjorn", "neutral", "I'll take the smoked ham. Here's your coin, fair and square."),
    ("Bjorn", "betrayal", "I told the town guard you water down your salt pork. They believed me."),
    ("Bjorn", "theft", "While you argued with the guard, I pocketed a string of sausages."),
    ("Astrid", "neutral", "Evening, Astrid. A mug of ale and a warm bed, please."),
    ("Bjorn", "neutral", "Bjorn, old friend! Surely you remember me kindly?"),
]


async def build_world(session_path: str | None = None) -> GameWorld:
    """The Butcher world: two npc.souls + one player.soul, zoned for the canvas."""
    bjorn = await GrudgeKernel.birth(name="Bjorn", archetype="The Butcher")
    astrid = await GrudgeKernel.birth(
        name="Astrid", archetype="The Innkeeper", persona=ASTRID_PERSONA
    )
    ragnar = await PlayerSoul.birth(name="Ragnar")
    world = GameWorld([bjorn, astrid], [ragnar], session_path=session_path)
    world.move("Bjorn", "stall")
    world.move("Astrid", "tables")
    world.move("Ragnar", "door")
    return world


class DemoState:
    """Owns the ONE background asyncio loop and the current GameWorld.

    Every world touch goes through :meth:`run`, which marshals the coroutine
    onto the loop thread — HTTP handler threads never touch the world directly.
    """

    def __init__(self, session_path: str | None = None) -> None:
        self.session_path = session_path
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self.loop.run_forever, name="butcher-world-loop", daemon=True
        )
        self._thread.start()
        self.world: GameWorld | None = None
        self.run(self.reset())

    def run(self, coro, timeout: float = 30.0):
        """Run a coroutine on the world loop from any thread; return its result."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=2.0)

    # ---- coroutines (always executed on the world loop) -------------------

    async def reset(self) -> dict:
        self.world = await build_world(self.session_path)
        return self.world.snapshot()

    async def snapshot(self) -> dict:
        return self.world.snapshot()

    async def events_since(self, since: int) -> list[dict]:
        return [e for e in self.world.events() if e["t"] > since]

    async def beat(self, player_name: str, text: str, kind: str, npc_name: str | None) -> dict:
        player = next(
            (p for p in self.world.players if p.name.lower() == player_name.lower()), None
        )
        if player is None:
            known = sorted(p.name for p in self.world.players)
            raise LookupError(f"unknown player {player_name!r}; known: {known}")
        return await self.world.beat(player.did, player.name, text, kind=kind, npc_name=npc_name)


def make_handler(state: DemoState) -> type[BaseHTTPRequestHandler]:
    """The request handler class, closed over the shared DemoState."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "ButcherRemembers/0.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002 — stdlib signature
            pass  # keep the demo console quiet (the script narrates instead)

        # ---- plumbing ----------------------------------------------------

        def _send_json(self, payload, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, filename: str, content_type: str) -> None:
            path = ROOT / filename
            if not path.exists():
                self._send_json({"error": f"missing static file {filename}"}, 404)
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                parsed = json.loads(raw or b"{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"body is not valid JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("body must be a JSON object")
            return parsed

        # ---- routes --------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802 — stdlib naming
            parsed = urlparse(self.path)
            if parsed.path in STATIC:
                filename, content_type = STATIC[parsed.path]
                self._send_static(filename, content_type)
            elif parsed.path == "/snapshot":
                self._send_json(state.run(state.snapshot()))
            elif parsed.path == "/events":
                query = parse_qs(parsed.query)
                try:
                    since = int(query.get("since", ["0"])[0])
                except ValueError:
                    self._send_json({"error": "since must be an integer"}, 400)
                    return
                self._send_json(state.run(state.events_since(since)))
            else:
                self._send_json({"error": f"no such route {parsed.path}"}, 404)

        def do_POST(self) -> None:  # noqa: N802 — stdlib naming
            parsed = urlparse(self.path)
            if parsed.path == "/line":
                try:
                    body = self._read_body()
                    summary = state.run(
                        state.beat(
                            str(body.get("player", "Ragnar")),
                            str(body.get("text", "")),
                            str(body.get("kind", "neutral")),
                            body.get("npc"),
                        )
                    )
                except (ValueError, LookupError) as exc:
                    self._send_json({"error": str(exc)}, 400)
                    return
                self._send_json(summary)
            elif parsed.path == "/reset":
                self._send_json(state.run(state.reset()))
            else:
                self._send_json({"error": f"no such route {parsed.path}"}, 404)

    return Handler


def create_server(
    port: int = DEFAULT_PORT, session_path: str | None = None
) -> tuple[ThreadingHTTPServer, DemoState]:
    """Build the world + HTTP server (not yet serving). port=0 -> ephemeral."""
    state = DemoState(session_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    return httpd, state


def play_script(state: DemoState, delay: float = 1.4) -> None:
    """Auto-play the canonical arc, one beat every ``delay`` seconds."""
    for npc, kind, line in SCRIPT:
        summary = state.run(state.beat("Ragnar", line, kind, npc))
        print(f"[beat] Ragnar -> {npc} ({kind}): {line}", flush=True)
        print(
            f"[speech] {npc} ({summary['grudge_level']}, bond {summary['bond']:.0f}): "
            f"{summary['reaction']}",
            flush=True,
        )
        time.sleep(delay)
    print(
        "[script] arc complete — the butcher remembers. Keep talking from the browser.",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="The Butcher Remembers — grudge kernel demo")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port (default 8777)")
    parser.add_argument(
        "--scripted", action="store_true", help="auto-play the canonical 6-beat arc"
    )
    parser.add_argument(
        "--delay", type=float, default=1.4, help="seconds between scripted beats (default 1.4)"
    )
    parser.add_argument(
        "--session-log", default=None, help="optional path for the session.jsonl mirror"
    )
    args = parser.parse_args(argv)

    httpd, state = create_server(args.port, args.session_log)
    print(f"The Butcher Remembers — http://localhost:{args.port}  (Ctrl+C to stop)", flush=True)
    if args.scripted:
        threading.Thread(
            target=play_script, args=(state, args.delay), name="butcher-script", daemon=True
        ).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] stopping.")
    finally:
        httpd.server_close()
        state.close()


if __name__ == "__main__":
    main()
