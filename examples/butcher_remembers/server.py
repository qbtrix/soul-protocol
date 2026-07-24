# server.py — "The Butcher Remembers": stdlib-only demo server that renders the
#   scripted grudge arc in a browser.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Serves the 2D canvas
#   client (index.html / app.js / style.css, same folder) and bridges HTTP onto
#   the Game Profile's GameWorld. Stdlib only: http.server.ThreadingHTTPServer +
#   json + urllib — no frameworks, no build step, no npm.
#
#   Async bridge: GrudgeKernel/GameWorld APIs are async, HTTP handlers are
#   threads. ONE background thread runs ONE asyncio event loop forever; every
#   handler marshals its coroutine onto it via asyncio.run_coroutine_threadsafe
#   and blocks on the result. That serializes all world mutation on one loop —
#   no per-request loops, no locks.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel, BD-2) — the 90-second
#   demo script. Added: POST /export_soul + /export_player (.soul downloads —
#   THE FILE beat), POST /import_soul (raw .soul bytes -> GrudgeKernel.awaken
#   -> replace_npc swaps the NPC in place; GameWorld stays frozen, the swap +
#   snapshot-cache refresh live HERE), GET /reputation (Astrid reads Ragnar's
#   portable player.soul reputation — the gut-punch beat), GET /cost (CostMeter
#   summary + deepseek-v3.2 projection + cost-per-player-hour; zeros when
#   templated), --engine templated|claude|deepseek (LLMDialogueEngine over the
#   local claude CLI or the DeepSeek chat API; missing DEEPSEEK_API_KEY falls
#   back to templated with a warning), and classify_kind() — a deterministic
#   keyword classifier so free-play POST /line needs no "kind" field.
#
#   Endpoints:
#     GET  /            -> index.html (plus /app.js, /style.css — whitelisted)
#     GET  /snapshot    -> GameWorld.snapshot() + {"engine": ...} (HUD bootstrap)
#     GET  /events?since=N -> world events with t > N (poll cursor)
#     GET  /cost        -> cost meter summary (zeros when templated)
#     GET  /reputation?npc=Astrid&player=Ragnar -> {line, notoriety}
#     POST /line {player, text, kind?, npc?} -> world.beat(...) summary
#                                               (kind absent -> classify_kind)
#     POST /reset       -> rebuild the world fresh, return its snapshot
#     POST /export_soul {npc?}      -> the NPC's .soul bytes as a download
#     POST /export_player {player?} -> the player's .player.soul as a download
#     POST /import_soul <raw .soul bytes> -> awaken + swap the same-named NPC
#
#   World: Bjorn (butcher, stall) + Astrid (innkeeper, tables) as GrudgeKernels,
#   Ragnar as the PlayerSoul (door). TemplatedDialogueEngine by DEFAULT —
#   deterministic and free. --scripted auto-plays the canonical arc (greet ->
#   trade -> betrayal -> theft -> Astrid control -> return to Bjorn, who
#   remembers) with a short delay between beats.
#
# Run:  uv run python examples/butcher_remembers/server.py --scripted
# Then: open http://localhost:8777

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from soul_protocol.profiles.game import (
    CostMeter,
    GameWorld,
    GrudgeKernel,
    LLMDialogueEngine,
    PlayerSoul,
    claude_cli_generate,
)

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


# ---------------------------------------------------------------------------
# Free-play machinery: kind auto-classifier, engine switch, cost meter, and
# the .soul import/export helpers (BD-2).
# ---------------------------------------------------------------------------

# The bottom-bar input has no "kind" dropdown, so free-play lines are
# classified with a tiny deterministic keyword map. First matching rule wins,
# checked in this order — theft before betrayal so "I pocketed it while you
# argued with the guard" reads as the theft it is. An explicit "kind" in the
# POST body always overrides the classifier.
_KIND_RULES: list[tuple[str, str]] = [
    (
        "theft",
        r"\b(steal|stole|stolen|pocket\w*|rob|robbed|robbing|pilfer\w*|swipe[ds]?|thief|theft)\b",
    ),
    (
        "betrayal",
        r"\b(betray\w*|lie[ds]?|lying|frame[ds]?|framing|guard|snitch\w*|traitor|sold\s+you\s+out)\b",
    ),
    (
        "insult",
        r"\b(insult\w*|maggot\w*|fool|idiot|coward|stink\w*|reek\w*|ugly|worthless|scum|swine|pig|dog|liar|wretch\w*)\b",
    ),
]


def classify_kind(text: str) -> str:
    """Classify a free-play line into a transgression kind. Deterministic, no LLM."""
    lowered = str(text).lower()
    for kind, pattern in _KIND_RULES:
        if re.search(pattern, lowered):
            return kind
    return "neutral"


async def deepseek_generate(prompt: str) -> str:
    """Generate a line via DeepSeek's OpenAI-compatible chat API (deepseek-chat).

    Stdlib-only: urllib runs in a worker thread (asyncio.to_thread) so the world
    loop never blocks on the network. Raises on missing key / HTTP / parse
    errors — LLMDialogueEngine catches and falls back to the template.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    payload = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.8,
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


def build_engine(requested: str):
    """Resolve --engine into (active_name, dialogue_engine | None, meter | None).

    templated -> (None, None): kernels default to the free deterministic
                 TemplatedDialogueEngine; /cost reports zeros.
    claude    -> LLMDialogueEngine over the local `claude` CLI (no API key,
                 ~20-40s per line), metered as the $0 "claude-cli" model so
                 token counts still accrue for the DeepSeek projection.
    deepseek  -> LLMDialogueEngine over the DeepSeek chat API, metered at
                 deepseek-v3.2 rates. Missing DEEPSEEK_API_KEY: print a
                 warning and fall back to templated — never crash the demo.
    """
    if requested == "claude":
        meter = CostMeter(claude_cli_generate, model="claude-cli")
        return "claude", LLMDialogueEngine(meter), meter
    if requested == "deepseek":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            print(
                "[engine] DEEPSEEK_API_KEY is not set — falling back to the "
                "templated engine (deterministic, $0).",
                flush=True,
            )
            return "templated", None, None
        meter = CostMeter(deepseek_generate, model="deepseek-v3.2")
        return "deepseek", LLMDialogueEngine(meter), meter
    return "templated", None, None


def kernel_named(world: GameWorld, npc_name: str | None) -> GrudgeKernel:
    """The named NPC kernel (case-insensitive), or the first when unnamed."""
    if not npc_name:
        return world.npcs[0]
    for kernel in world.npcs:
        if kernel.npc_name.lower() == str(npc_name).lower():
            return kernel
    known = sorted(k.npc_name for k in world.npcs)
    raise LookupError(f"unknown npc {npc_name!r}; known: {known}")


def player_named(world: GameWorld, player_name: str | None) -> PlayerSoul:
    """The named player soul (case-insensitive), or the first when unnamed."""
    if not player_name:
        return world.players[0]
    for player in world.players:
        if player.name.lower() == str(player_name).lower():
            return player
    known = sorted(p.name for p in world.players)
    raise LookupError(f"unknown player {player_name!r}; known: {known}")


async def replace_npc(world: GameWorld, kernel: GrudgeKernel) -> str:
    """Swap the same-named NPC for an awakened kernel — demo-side on purpose.

    GameWorld (GP-5) stays frozen: the swap lives here, mutating world.npcs in
    place (zones are keyed by name, so the zone sticks) and refreshing the two
    private snapshot caches so the HUD immediately shows the IMPORTED grudge
    state instead of the pre-import one. Emits nothing into the event stream —
    the client re-bootstraps from /snapshot after an import.
    """
    for i, existing in enumerate(world.npcs):
        if existing.npc_name == kernel.npc_name:
            world.npcs[i] = kernel
            break
    else:
        known = sorted(k.npc_name for k in world.npcs)
        raise LookupError(f"imported soul {kernel.npc_name!r} matches no npc; known: {known}")

    for player in world.players:
        key = (kernel.npc_name, player.did)
        world._grudge_levels[key] = await kernel.grudge_level(player.did)
        grievances = await kernel.grievances(player.did)
        if grievances:
            # The HUD's "remembers: ..." line — cite the worst recovered wrong,
            # stripped of the machine marker prefix.
            worst = max(grievances, key=lambda g: g.severity)
            world._last_grievance[key] = worst.content.split(" wronged me: ", 1)[-1]
        else:
            world._last_grievance.pop(key, None)
    return kernel.npc_name


async def build_world(session_path: str | None = None, dialogue_engine=None) -> GameWorld:
    """The Butcher world: two npc.souls + one player.soul, zoned for the canvas."""
    bjorn = await GrudgeKernel.birth(
        name="Bjorn", archetype="The Butcher", dialogue_engine=dialogue_engine
    )
    astrid = await GrudgeKernel.birth(
        name="Astrid",
        archetype="The Innkeeper",
        persona=ASTRID_PERSONA,
        dialogue_engine=dialogue_engine,
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

    def __init__(self, session_path: str | None = None, engine: str = "templated") -> None:
        self.session_path = session_path
        self.engine_name, self.dialogue_engine, self.meter = build_engine(engine)
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

    def _snapshot(self) -> dict:
        """world.snapshot() stamped with the active engine (the client uses it
        to decide whether the cost overlay is meaningful)."""
        snap = self.world.snapshot()
        snap["engine"] = self.engine_name
        return snap

    async def reset(self) -> dict:
        self.world = await build_world(self.session_path, dialogue_engine=self.dialogue_engine)
        if self.meter is not None:
            self.world.attach_meter(self.meter)
        return self._snapshot()

    async def snapshot(self) -> dict:
        return self._snapshot()

    async def export_soul(self, npc_name: str | None) -> tuple[str, bytes]:
        """Export one NPC to .soul bytes — THE artifact moment of the demo."""
        kernel = kernel_named(self.world, npc_name)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.soul"
            await kernel.export(str(path))
            data = path.read_bytes()
        return f"{kernel.npc_name.lower()}.soul", data

    async def export_player(self, player_name: str | None) -> tuple[str, bytes]:
        """Export a player.soul — the portable reputation the player OWNS."""
        player = player_named(self.world, player_name)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "player.soul"
            await player.export(str(path))
            data = path.read_bytes()
        return f"{player.name.lower()}.player.soul", data

    async def import_soul(self, data: bytes) -> dict:
        """Awaken a .soul from raw bytes and swap it in for the same-named NPC."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "import.soul"
            path.write_bytes(data)
            kernel = await GrudgeKernel.awaken(str(path), dialogue_engine=self.dialogue_engine)
        if kernel.npc_name == "Astrid":
            kernel.persona = ASTRID_PERSONA  # persona is not persisted in the .soul
        replaced = await replace_npc(self.world, kernel)
        return {"replaced": replaced, "snapshot": self._snapshot()}

    async def reputation(self, npc_name: str, player_name: str) -> dict:
        """THE gut-punch: a never-wronged NPC reads the player's portable
        reputation off their player.soul and reacts to it."""
        kernel = kernel_named(self.world, npc_name)
        player = player_named(self.world, player_name)
        line, notoriety = await kernel.react_to_reputation(player)
        return {
            "npc": kernel.npc_name,
            "player": player.name,
            "line": line,
            "notoriety": notoriety,
        }

    async def cost(self) -> dict:
        """The cost readout: meter summary + DeepSeek projection. Zeros/nulls
        when the templated engine is active (no meter, nothing to meter)."""
        if self.meter is None:
            return {
                "engine": self.engine_name,
                "model": None,
                "calls": 0,
                "cached_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "total_cost": 0.0,
                "avg_latency": 0.0,
                "cost_per_100_lines": 0.0,
                "projected_deepseek": 0.0,
                "cost_per_player_hour": 0.0,
            }
        summary = self.meter.summary()
        summary["engine"] = self.engine_name
        summary["projected_deepseek"] = self.meter.project("deepseek-v3.2")
        summary["cost_per_player_hour"] = self.meter.cost_per_player_hour()
        return summary

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

        def _read_raw(self) -> bytes:
            """The raw request body — /import_soul takes the .soul bytes as-is."""
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else b""

        def _send_file(self, filename: str, data: bytes) -> None:
            """Send bytes as a browser download (Content-Disposition attachment)."""
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

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
            elif parsed.path == "/cost":
                self._send_json(state.run(state.cost()))
            elif parsed.path == "/reputation":
                query = parse_qs(parsed.query)
                npc = query.get("npc", ["Astrid"])[0]
                player = query.get("player", ["Ragnar"])[0]
                try:
                    self._send_json(state.run(state.reputation(npc, player)))
                except LookupError as exc:
                    self._send_json({"error": str(exc)}, 400)
            else:
                self._send_json({"error": f"no such route {parsed.path}"}, 404)

        def do_POST(self) -> None:  # noqa: N802 — stdlib naming
            parsed = urlparse(self.path)
            if parsed.path == "/line":
                try:
                    body = self._read_body()
                    text = str(body.get("text", ""))
                    # Free-play lines carry no "kind": classify deterministically.
                    # An explicit kind (the panel dropdown) always wins.
                    kind = str(body.get("kind") or classify_kind(text))
                    summary = state.run(
                        state.beat(
                            str(body.get("player", "Ragnar")),
                            text,
                            kind,
                            body.get("npc"),
                        )
                    )
                except (ValueError, LookupError) as exc:
                    self._send_json({"error": str(exc)}, 400)
                    return
                self._send_json(summary)
            elif parsed.path == "/reset":
                self._send_json(state.run(state.reset()))
            elif parsed.path == "/export_soul":
                try:
                    body = self._read_body()
                    filename, data = state.run(state.export_soul(body.get("npc")))
                except (ValueError, LookupError) as exc:
                    self._send_json({"error": str(exc)}, 400)
                    return
                self._send_file(filename, data)
            elif parsed.path == "/export_player":
                try:
                    body = self._read_body()
                    filename, data = state.run(state.export_player(body.get("player")))
                except (ValueError, LookupError) as exc:
                    self._send_json({"error": str(exc)}, 400)
                    return
                self._send_file(filename, data)
            elif parsed.path == "/import_soul":
                raw = self._read_raw()
                if not raw.startswith(b"PK"):
                    self._send_json({"error": "body must be raw .soul bytes (a zip archive)"}, 400)
                    return
                try:
                    result = state.run(state.import_soul(raw))
                except LookupError as exc:
                    self._send_json({"error": str(exc)}, 400)
                    return
                except Exception as exc:  # corrupt archive, bad soul payload, ...
                    self._send_json({"error": f"could not awaken soul: {exc}"}, 400)
                    return
                self._send_json(result)
            else:
                self._send_json({"error": f"no such route {parsed.path}"}, 404)

    return Handler


def create_server(
    port: int = DEFAULT_PORT, session_path: str | None = None, engine: str = "templated"
) -> tuple[ThreadingHTTPServer, DemoState]:
    """Build the world + HTTP server (not yet serving). port=0 -> ephemeral."""
    state = DemoState(session_path, engine=engine)
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
    parser.add_argument(
        "--engine",
        choices=["templated", "claude", "deepseek"],
        default="templated",
        help=(
            "dialogue backend: templated (deterministic, $0, default), "
            "claude (local claude CLI, no key, ~20-40s/line), "
            "deepseek (DeepSeek chat API, needs DEEPSEEK_API_KEY)"
        ),
    )
    args = parser.parse_args(argv)

    httpd, state = create_server(args.port, args.session_log, engine=args.engine)
    print(
        f"The Butcher Remembers — http://localhost:{args.port}  "
        f"[engine: {state.engine_name}]  (Ctrl+C to stop)",
        flush=True,
    )
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
