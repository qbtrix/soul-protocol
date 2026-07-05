# server.py — NEM-4: "SAURON'S ARMY", a stdlib-only demo server that renders the
#   Nemesis-System warband as a playable browser game.
#
# Created: 2026-07-05 (feat/nemesis-warband) — Serves the grimdark army-board
#   client (index.html / app.js / style.css, same folder) and bridges HTTP onto
#   the Warband + WarbandDirector engine (warband.py / nemesis_director.py, both
#   on the unchanged soul_protocol.profiles.game package). Stdlib only:
#   http.server.ThreadingHTTPServer + json + urllib + zipfile — no frameworks,
#   no build step, no npm.
#
#   Async bridge (mirrors the Butcher demo): Warband/GrudgeKernel APIs are async,
#   HTTP handlers are threads. ONE background thread runs ONE asyncio event loop
#   forever; every handler marshals its coroutine onto it via
#   asyncio.run_coroutine_threadsafe and blocks on the result. That serializes
#   all warband mutation on one loop — no per-request loops, no locks.
#
#   Events: there is no GameWorld here, so this server keeps its OWN append-only
#   event log with a monotonic `t` cursor. Every confront / tick / recruit /
#   revenge / power-struggle / death pushes an event; the client polls
#   GET /events?since=N and animates from the tail.
#
#   Endpoints:
#     GET  /              -> index.html (plus /app.js, /style.css — whitelisted)
#     GET  /board         -> the army snapshot: members (did, name, epithet, rank
#                            label, alive, grudge level+bond+last grievance toward
#                            the player, rivalries[names]) + director phase + rep.
#     GET  /events?since=N-> event stream with t > N (poll cursor)
#     GET  /reputation    -> Talion's notoriety + portable deeds
#     POST /confront {member_did, player_won} -> warband.clash(...) outcome
#                            (rank change, kill, taunt via the member's engine,
#                            rivalry_triggered) + emitted events
#     POST /tick          -> director.tick(...) -> a revenge beat / power-struggle
#                            beat / nothing (RELAX breather)
#     POST /recruit       -> a new member reads Talion's reputation and joins
#     POST /export_member {did} -> that member's .soul (Content-Disposition)
#     POST /export_warband      -> a .zip of every member's .soul
#
#   Engines: --engine templated|claude|deepseek. templated (default) => each
#     member speaks through the grimdark WarbandDialogueEngine (deterministic,
#     $0). claude => LLMDialogueEngine over the local `claude` CLI, per member,
#     persona-driven. deepseek => the DeepSeek chat API (needs DEEPSEEK_API_KEY;
#     missing key falls back to templated with a warning). A CostMeter is
#     attached when an LLM engine is active so /board can report spend.
#
# Run:  uv run python examples/nemesis_warband/server.py
# Then: open http://localhost:8778

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import tempfile
import threading
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from soul_protocol.profiles.game import (
    CostMeter,
    LLMDialogueEngine,
    PlayerSoul,
)

# Dual-mode imports: this file is imported as a module by the tests
# (examples.nemesis_warband.server) AND run directly as a script
# (``uv run python examples/nemesis_warband/server.py``). Relative imports work
# only in the package case, so fall back to absolute imports — after putting the
# repo root on sys.path — when run as a top-level script.
try:  # package / test import
    from .nemesis_director import WarbandDirector
    from .warband import Warband
    from .warband_voice import WarbandDialogueEngine
except ImportError:  # run as a script: `python examples/nemesis_warband/server.py`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from examples.nemesis_warband.nemesis_director import WarbandDirector
    from examples.nemesis_warband.warband import Warband
    from examples.nemesis_warband.warband_voice import WarbandDialogueEngine

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8778  # the Butcher demo owns 8777; this is its own port.
PLAYER_NAME = "Talion"
WARBAND_SIZE = 6

# Static whitelist: path -> (filename in this folder, content type). Nothing
# else on disk is reachable — no directory-traversal surface.
STATIC: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}

# Fresh recruits cycle through these grimdark names/epithets so each new orc that
# joins the war-camp is distinct without any external data.
_RECRUIT_NAMES = ["Zog", "Grfull", "Morgash", "Urfang", "Brakka", "Snaga", "Golm", "Yazgar"]
_RECRUIT_EPITHETS = [
    "the Newcomer",
    "Bone-Eater",
    "the Scarred",
    "the Rat",
    "Foul-Tongue",
    "the Sudden",
    "the Green",
    "Ash-Maw",
]


# ---------------------------------------------------------------------------
# LLM backend for --engine deepseek (stdlib urllib; claude uses the package's
# claude_cli_generate). Both feed a per-member LLMDialogueEngine.
# ---------------------------------------------------------------------------
async def deepseek_generate(prompt: str) -> str:
    """Generate a line via DeepSeek's OpenAI-compatible chat API (deepseek-chat).

    Stdlib-only: urllib runs in a worker thread (asyncio.to_thread) so the world
    loop never blocks on the network. Raises on missing key / HTTP / parse
    errors — LLMDialogueEngine catches and falls back to the (warband) template.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    payload = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.85,
        }
    ).encode("utf-8")

    def _call() -> str:
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    return (await asyncio.to_thread(_call)).strip()


def build_engine(requested: str) -> tuple[str, object | None]:
    """Resolve --engine into (active_name, meter | None).

    The meter, when present, wraps the chosen ``generate`` and is what each
    member's LLMDialogueEngine calls — so token counts accrue across the whole
    warband. templated => (·, None): members use the free WarbandDialogueEngine.
    deepseek with no key => warn and fall back to templated.
    """
    from soul_protocol.profiles.game import claude_cli_generate

    if requested == "claude":
        return "claude", CostMeter(claude_cli_generate, model="claude-cli")
    if requested == "deepseek":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            print(
                "[engine] DEEPSEEK_API_KEY is not set — falling back to the "
                "warband voice (deterministic, $0).",
                flush=True,
            )
            return "templated", None
        return "deepseek", CostMeter(deepseek_generate, model="deepseek-v3.2")
    return "templated", None


def make_voice_factory(meter: object | None):
    """A ``voice_factory(name, epithet, rank_label) -> DialogueEngine`` for forge.

    With no meter, every member gets the deterministic grimdark
    WarbandDialogueEngine. With a meter, every member gets an LLMDialogueEngine
    over the metered generate — but the LLM engine falls back to the PACKAGE's
    templated (butcher) voice on error, which is wrong for orcs, so we hand the
    LLM engine our WarbandDialogueEngine as the fallback instead (constructed
    with this member's identity). That keeps a flaky model grimdark, never
    butcher-flavored.
    """
    if meter is None:
        return lambda name, epithet, rl: WarbandDialogueEngine(name, epithet, rl)

    def factory(name: str, epithet: str, rl: str):
        engine = LLMDialogueEngine(meter)
        # Swap the LLM engine's fallback from the butcher template to THIS
        # member's warband voice, so a model failure still sounds like an orc.
        engine._fallback = WarbandDialogueEngine(name, epithet, rl)
        return engine

    return factory


# ---------------------------------------------------------------------------
# The demo state: the ONE background loop, the Warband, the director, the event
# log. Every warband touch goes through run() onto the loop thread.
# ---------------------------------------------------------------------------
class DemoState:
    def __init__(self, engine: str = "templated") -> None:
        self.engine_name, self.meter = build_engine(engine)
        self._voice_factory = make_voice_factory(self.meter)
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self.loop.run_forever, name="warband-world-loop", daemon=True
        )
        self._thread.start()
        self.warband: Warband | None = None
        self.director: WarbandDirector | None = None
        self.player: PlayerSoul | None = None
        # Append-only event log + monotonic cursor (there's no GameWorld here).
        self._events: list[dict] = []
        self._t = 0
        self.run(self.reset())

    def run(self, coro, timeout: float = 120.0):
        """Run a coroutine on the world loop from any thread; return its result.

        The 120s timeout is generous on purpose: an LLM engine (``--engine
        claude``) can take 20-40s to produce a single taunt, and a confront may
        speak more than once.
        """
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=2.0)

    # ---- event log --------------------------------------------------------

    def _emit(self, kind: str, **data) -> dict:
        """Append one event with the next `t` cursor and return it."""
        self._t += 1
        event = {"t": self._t, "kind": kind, **data}
        self._events.append(event)
        return event

    # ---- coroutines (always executed on the world loop) -------------------

    async def reset(self) -> dict:
        self.player = await PlayerSoul.birth(name=PLAYER_NAME)
        self.warband = await Warband.forge(
            self.player, size=WARBAND_SIZE, voice_factory=self._voice_factory
        )
        self.director = WarbandDirector()
        self._events = []
        self._t = 0
        self._emit("forged", size=WARBAND_SIZE, player=PLAYER_NAME)
        return await self._board()

    async def _board(self) -> dict:
        """The SAURON'S ARMY snapshot: enriched board rows (with DID) + director
        phase + the player's reputation + the active engine."""
        rows = await self.warband.board()
        # board() rows carry name/epithet/rank/alive/grudge_level/bond/
        # last_grievance/rivalries but not the DID (needed to target confront /
        # export), so zip the DID in from the member list (stable order).
        for row, member in zip(rows, self.warband.members):
            row["did"] = member.did
            row["rank_label"] = member.rank_label  # explicit label alongside `rank`
        deeds, notoriety = await self.player.reputation()
        return {
            "player": {"name": self.player.name, "notoriety": notoriety, "deeds": deeds},
            "members": rows,
            "phase": self.director.phase,
            "engine": self.engine_name,
            "cursor": self._t,
        }

    async def board(self) -> dict:
        return await self._board()

    async def reputation(self) -> dict:
        deeds, notoriety = await self.player.reputation()
        return {"player": self.player.name, "notoriety": notoriety, "deeds": deeds}

    async def events_since(self, since: int) -> list[dict]:
        return [e for e in self._events if e["t"] > since]

    async def confront(self, member_did: str, player_won: bool) -> dict:
        """Resolve a clash and emit the beat into the event log."""
        member = self.warband.member(member_did)  # KeyError -> 400 in the handler
        note = "in the war-pit" if player_won else "and left you bleeding"
        beat = await self.warband.clash(
            member_did, self.player.did, player_won=player_won, note=note
        )
        self._emit(
            "confront",
            member=beat["member"],
            epithet=beat["epithet"],
            outcome=beat["outcome"],
            rank_change=beat["rank_change"],
            rank_label=beat["rank_label"],
            killed=beat["killed"],
            alive=beat["alive"],
            taunt=beat["taunt"],
            rivalry_triggered=beat["rivalry_triggered"],
        )
        if beat["killed"]:
            self._emit("death", member=beat["member"], epithet=beat["epithet"])
        beat["board"] = await self._board()
        return beat

    async def tick(self) -> dict:
        """Advance the war one beat: a revenge beat, a power struggle, or the
        RELAX breather (nothing). Emit whatever fired."""
        beat = await self.director.tick(self.warband, self.player.did)
        if beat.get("revenge"):
            r = beat["revenge"]
            self._emit(
                "revenge",
                member=r["member"],
                epithet=r["epithet"],
                grudge_level=r["grudge_level"],
                bond=r["bond"],
                taunt=r["taunt"],
            )
        if beat.get("power_struggle"):
            ps = beat["power_struggle"]
            self._emit(
                "power_struggle",
                winner=ps["winner"],
                winner_rank=ps["winner_rank"],
                loser=ps["loser"],
                loser_rank=ps["loser_rank"],
                loser_killed=ps["loser_killed"],
            )
            if ps["loser_killed"]:
                self._emit("death", member=ps["loser"], epithet="")
        beat["board"] = await self._board()
        return beat

    async def recruit(self) -> dict:
        """A fresh orc reads Talion's reputation and joins the war-camp."""
        i = len(self.warband.members)
        name = _RECRUIT_NAMES[i % len(_RECRUIT_NAMES)]
        epithet = _RECRUIT_EPITHETS[i % len(_RECRUIT_EPITHETS)]
        rec = await self.warband.recruit(name, epithet)
        self._emit(
            "recruit",
            member=rec["member"],
            epithet=rec["epithet"],
            rank=rec["rank"],
            first_line=rec["first_line"],
            notoriety=rec["notoriety"],
        )
        rec["board"] = await self._board()
        return rec

    async def export_member(self, member_did: str) -> tuple[str, bytes]:
        """Export one member to .soul bytes — a portable nemesis you can carry."""
        member = self.warband.member(member_did)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nemesis.soul"
            await member.kernel.export(str(path))
            data = path.read_bytes()
        safe = member.name.lower().encode("ascii", "ignore").decode() or "nemesis"
        return f"{safe}.soul", data

    async def export_warband(self) -> tuple[str, bytes]:
        """Export EVERY member's .soul into one .zip — the whole army, portable."""
        buffer = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for idx, member in enumerate(self.warband.members):
                    path = Path(tmp) / f"member_{idx}.soul"
                    await member.kernel.export(str(path))
                    safe = member.name.lower().encode("ascii", "ignore").decode() or "orc"
                    archive.write(path, arcname=f"{idx:02d}_{safe}.soul")
        return "warband.zip", buffer.getvalue()


# ---------------------------------------------------------------------------
# HTTP handler.
# ---------------------------------------------------------------------------
def make_handler(state: DemoState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SauronsArmy/0.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002 — stdlib sig
            pass  # keep the demo console quiet

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

        def _send_file(self, filename: str, data: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

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

        # ---- routes ------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802 — stdlib naming
            parsed = urlparse(self.path)
            if parsed.path in STATIC:
                filename, content_type = STATIC[parsed.path]
                self._send_static(filename, content_type)
            elif parsed.path == "/board":
                self._send_json(state.run(state.board()))
            elif parsed.path == "/events":
                query = parse_qs(parsed.query)
                try:
                    since = int(query.get("since", ["0"])[0])
                except ValueError:
                    self._send_json({"error": "since must be an integer"}, 400)
                    return
                self._send_json(state.run(state.events_since(since)))
            elif parsed.path == "/reputation":
                self._send_json(state.run(state.reputation()))
            else:
                self._send_json({"error": f"no such route {parsed.path}"}, 404)

        def do_POST(self) -> None:  # noqa: N802 — stdlib naming
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/confront":
                    body = self._read_body()
                    member_did = str(body.get("member_did", ""))
                    if not member_did:
                        self._send_json({"error": "member_did is required"}, 400)
                        return
                    player_won = bool(body.get("player_won", False))
                    self._send_json(state.run(state.confront(member_did, player_won)))
                elif parsed.path == "/tick":
                    self._send_json(state.run(state.tick()))
                elif parsed.path == "/recruit":
                    self._send_json(state.run(state.recruit()))
                elif parsed.path == "/reset":
                    self._send_json(state.run(state.reset()))
                elif parsed.path == "/export_member":
                    body = self._read_body()
                    did = str(body.get("did", ""))
                    if not did:
                        self._send_json({"error": "did is required"}, 400)
                        return
                    filename, data = state.run(state.export_member(did))
                    self._send_file(filename, data, "application/octet-stream")
                elif parsed.path == "/export_warband":
                    filename, data = state.run(state.export_warband())
                    self._send_file(filename, data, "application/zip")
                else:
                    self._send_json({"error": f"no such route {parsed.path}"}, 404)
            except (ValueError, LookupError, KeyError) as exc:
                # KeyError from warband.member(did) => unknown member; ValueError
                # from a bad body; LookupError kept for symmetry with the API.
                self._send_json({"error": str(exc)}, 400)

    return Handler


def create_server(
    port: int = DEFAULT_PORT, engine: str = "templated"
) -> tuple[ThreadingHTTPServer, DemoState]:
    """Build the warband + HTTP server (not yet serving). port=0 -> ephemeral."""
    state = DemoState(engine=engine)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    return httpd, state


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SAURON'S ARMY — Nemesis warband demo")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port (default 8778)")
    parser.add_argument(
        "--engine",
        choices=["templated", "claude", "deepseek"],
        default="templated",
        help=(
            "dialogue backend: templated (grimdark WarbandDialogueEngine, $0, "
            "default), claude (local claude CLI, no key, ~20-40s/line, per "
            "member), deepseek (DeepSeek chat API, needs DEEPSEEK_API_KEY)"
        ),
    )
    args = parser.parse_args(argv)

    httpd, state = create_server(args.port, engine=args.engine)
    print(
        f"SAURON'S ARMY — http://localhost:{args.port}  "
        f"[engine: {state.engine_name}]  (Ctrl+C to stop)",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] stopping.")
    finally:
        httpd.server_close()
        state.close()


if __name__ == "__main__":
    main()
