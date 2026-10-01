# gateway/app.py - Minimal Starlette REST API + OpenAI-compatible LLM proxy over a Soul.
# Created: 2026-05 - Exposes a thin JSON-over-HTTP surface (health, state,
#   remember, recall, observe, turn) plus POST /v1/chat/completions that
#   auto-recalls memories, injects them into the system prompt, forwards to an
#   upstream LLM, and auto-observes the turn. Starlette + httpx keep it
#   dependency-light (both already present as FastMCP transitive deps).

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from ..runtime.soul import Soul
from ..runtime.types import Interaction, MemoryType
from ._dashboard import DASHBOARD_HTML
from ._legal import FAVICON_SVG, PRIVACY_HTML, TERMS_HTML

try:
    from ..runtime.middleware import AutoObserveMiddleware
except ImportError:  # auto_observe.py not yet on this branch

    class AutoObserveMiddleware:  # type: ignore[no-redef]
        """Minimal inline fallback so the gateway works standalone."""

        def __init__(self, soul: Soul, **_kw: object) -> None:
            self._soul = soul

        async def turn(
            self,
            user_input: str,
            agent_output: str = "",
            *,
            query: str | None = None,
            limit: int | None = None,
            user_id: str | None = None,
            layer: str | None = None,
            domain: str | None = None,
            channel: str | None = None,
        ) -> dict:
            memories: list[dict] = []
            if query:
                results = await self._soul.recall(
                    query,
                    limit=limit if limit is not None else 5,
                    user_id=user_id,
                    layer=layer,
                    domain=domain,
                )
                memories = [
                    {
                        "id": r.id,
                        "type": r.type.value,
                        "layer": r.layer or r.type.value,
                        "domain": r.domain or "default",
                        "content": r.content,
                        "importance": r.importance,
                        "emotion": r.emotion,
                        "user_id": r.user_id,
                    }
                    for r in results
                ]
            await self._soul.observe(
                Interaction(
                    user_input=user_input,
                    agent_output=agent_output,
                    channel=channel or "auto",
                ),
                user_id=user_id,
                domain=domain or "default",
            )
            state = self._soul.state
            return {
                "soul": self._soul.name,
                "mood": state.mood.value,
                "energy": round(state.energy, 1),
                "user_id": user_id,
                "recalled": len(memories),
                "memories": memories,
            }


logger = logging.getLogger(__name__)

# Keep references to scheduled observe tasks so fire-and-forget work is not
# garbage-collected before it completes.
_background_tasks: set[asyncio.Task] = set()


def _bond_label(strength: float) -> str:
    """Map a bond strength (0-100) to a human-readable relationship label."""
    if strength >= 80:
        return "Trusted companion"
    if strength >= 60:
        return "Close friend"
    if strength >= 40:
        return "Friend"
    if strength >= 20:
        return "Acquaintance"
    return "Stranger"


async def _body(request: Request) -> dict[str, Any]:
    """Parse a JSON body, tolerating missing/invalid JSON as an empty dict."""
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _json(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def _memories_payload(results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "type": r.type.value,
            "layer": r.layer or r.type.value,
            "domain": r.domain or "default",
            "content": r.content,
            "importance": r.importance,
            "emotion": r.emotion,
            "user_id": r.user_id,
        }
        for r in results
    ]


@dataclass
class LLMProxyConfig:
    """Configuration for forwarding chat requests to an upstream LLM."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4"
    recall_limit: int = 5

    @classmethod
    def from_env(cls) -> LLMProxyConfig:
        return cls(
            base_url=os.environ.get("SOUL_LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ.get("SOUL_LLM_API_KEY", ""),
            model=os.environ.get("SOUL_LLM_MODEL", "gpt-4"),
        )


def _last_user_message(messages: list[Any]) -> str:
    """Return the text of the most recent user message, if any."""
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")]
            return " ".join(parts)
    return ""


def _assistant_reply(response_json: dict[str, Any]) -> str:
    """Extract the assistant's text from an OpenAI-style completion response."""
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("text"))
    return ""


def _format_memories(memories: list[Any]) -> str:
    """Render recalled memories as an injectable system-prompt block."""
    if not memories:
        return ""
    lines = ["[Relevant memories - use these to personalize the response when applicable:]"]
    for m in memories:
        layer = m.layer or m.type.value
        lines.append(f"- ({layer}) {m.content.strip()}")
    return "\n".join(lines)


def _observe_coro(soul: Soul, user_input: str, agent_output: str):
    """Return a coroutine that saves a turn via AutoObserveMiddleware (never raises)."""

    async def _run() -> None:
        try:
            await AutoObserveMiddleware(soul).turn(user_input, agent_output)
        except Exception:
            logger.exception("auto-observe failed")

    return _run()


def create_app(
    soul: Soul,
    *,
    llm_config: LLMProxyConfig | None = None,
    llm_client: httpx.AsyncClient | None = None,
    observe_mode: str = "fire_and_forget",
) -> Starlette:
    """Build a Starlette app exposing a Soul over REST + an OpenAI-compatible LLM proxy.

    ``POST /v1/chat/completions`` auto-recalls relevant memories, injects them
    into the system prompt, forwards to the upstream LLM, then auto-observes
    the turn.

    Args:
        soul: The soul backing recall/observe.
        llm_config: Upstream LLM config (defaults to ``LLMProxyConfig.from_env()``).
        llm_client: Optional ``httpx.AsyncClient`` (inject a mock transport in tests).
        observe_mode: ``"fire_and_forget"`` (default) or ``"await"`` for tests.

    Usage::

        from soul_protocol.gateway import create_app
        import uvicorn
        uvicorn.run(create_app(soul), host="127.0.0.1", port=8000)
    """
    config = llm_config or LLMProxyConfig.from_env()
    owns_client = llm_client is None

    @asynccontextmanager
    async def lifespan(app: Starlette):
        app.state.llm_client = llm_client or httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(60.0),
        )
        yield
        if owns_client and app.state.llm_client is not None:
            await app.state.llm_client.aclose()

    async def health(request: Request) -> JSONResponse:
        return _json({"status": "ok", "soul": soul.name, "did": soul.did})

    async def state(request: Request) -> JSONResponse:
        s = soul.state
        return _json(
            {
                "soul": soul.name,
                "mood": s.mood.value,
                "energy": round(s.energy, 1),
                "focus": s.focus,
                "social_battery": round(s.social_battery, 1),
                "lifecycle": soul.lifecycle.value,
            }
        )

    async def remember(request: Request) -> JSONResponse:
        body = await _body(request)
        content = body.get("content")
        if not content:
            return _json({"error": "content is required"}, status=400)
        try:
            memory_type = MemoryType(body.get("memory_type", "semantic"))
        except ValueError:
            return _json(
                {"error": f"invalid memory_type: {body.get('memory_type')}"},
                status=400,
            )
        importance = body.get("importance")
        importance = max(1, min(10, int(importance) if importance is not None else 5))
        memory_id = await soul.remember(
            content,
            type=memory_type,
            importance=importance,
            emotion=body.get("emotion"),
            domain=body.get("domain", "default"),
        )
        return _json({"memory_id": memory_id, "soul": soul.name})

    async def recall(request: Request) -> JSONResponse:
        body = await _body(request)
        query = body.get("query", "")
        if not query:
            return _json({"error": "query is required"}, status=400)
        limit = body.get("limit")
        limit = int(limit) if limit is not None else 5
        results = await soul.recall(
            query,
            limit=limit,
            user_id=body.get("user_id"),
            layer=body.get("layer"),
            domain=body.get("domain"),
        )
        return _json(
            {"count": len(results), "soul": soul.name, "memories": _memories_payload(results)}
        )

    async def observe(request: Request) -> JSONResponse:
        body = await _body(request)
        user_input = body.get("user_input")
        if not user_input:
            return _json({"error": "user_input is required"}, status=400)
        await soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=body.get("agent_output", ""),
            ),
            user_id=body.get("user_id"),
        )
        s = soul.state
        return _json(
            {
                "status": "observed",
                "soul": soul.name,
                "mood": s.mood.value,
                "energy": round(s.energy, 1),
            }
        )

    async def turn(request: Request) -> JSONResponse:
        body = await _body(request)
        user_input = body.get("user_input")
        if not user_input:
            return _json({"error": "user_input is required"}, status=400)
        result = await AutoObserveMiddleware(soul).turn(
            user_input,
            body.get("agent_output", ""),
            query=body.get("query"),
            limit=body.get("limit"),
            user_id=body.get("user_id"),
            layer=body.get("layer"),
            domain=body.get("domain"),
            channel=body.get("channel"),
        )
        result["status"] = "observed"
        return _json(result)

    async def chat_completions(request: Request) -> JSONResponse:
        body = await _body(request)
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return _json({"error": "messages is required"}, status=400)
        if body.get("stream"):
            return _json({"error": "streaming is not supported by the proxy yet"}, status=400)

        user_text = _last_user_message(messages)

        # AUTO-RECALL: find memories relevant to the latest user message and
        # inject them into the system prompt.
        memory_block = ""
        if user_text:
            memories = await soul.recall(user_text, limit=config.recall_limit)
            memory_block = _format_memories(memories)

        enriched = dict(body)
        enriched_messages = [dict(m) if isinstance(m, dict) else m for m in messages]
        if memory_block:
            enriched_messages.insert(0, {"role": "system", "content": memory_block})
        enriched["messages"] = enriched_messages
        enriched["model"] = body.get("model") or config.model

        # FORWARD to the upstream LLM.
        client = request.app.state.llm_client
        url = config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        try:
            upstream = await client.post(url, json=enriched, headers=headers)
            upstream.raise_for_status()
            response_json = upstream.json()
        except httpx.HTTPError as exc:
            return _json({"error": f"upstream LLM error: {exc}"}, status=502)

        # AUTO-OBSERVE: save the turn. Fire-and-forget by default so the
        # response is never delayed by memory writes.
        assistant_reply = _assistant_reply(response_json)
        if user_text or assistant_reply:
            coro = _observe_coro(soul, user_text, assistant_reply)
            if observe_mode == "await":
                await coro
            else:
                task = asyncio.create_task(coro)
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

        return JSONResponse(response_json, status_code=upstream.status_code)

    # ---- Dashboard v2 (multi-tab interactive web UI) ----

    def _list_memories() -> list[Any]:
        """Return all active memories across the four built-in layers."""
        memories: list[Any] = []
        for layer_name in ("episodic", "semantic", "procedural", "social"):
            memories.extend(soul._memory.layer(layer_name).entries())
        return memories

    async def dashboard(request: Request) -> HTMLResponse:
        return HTMLResponse(DASHBOARD_HTML)

    async def privacy(request: Request) -> HTMLResponse:
        return HTMLResponse(PRIVACY_HTML)

    async def terms(request: Request) -> HTMLResponse:
        return HTMLResponse(TERMS_HTML)

    async def favicon(request: Request) -> Response:
        return Response(
            FAVICON_SVG,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    async def api_personality(request: Request) -> JSONResponse:
        p = soul.dna.personality
        return _json(
            {
                "soul": soul.name,
                "archetype": soul.identity.archetype,
                "values": list(soul.identity.core_values),
                "ocean": {
                    "openness": float(p.openness),
                    "conscientiousness": float(p.conscientiousness),
                    "extraversion": float(p.extraversion),
                    "agreeableness": float(p.agreeableness),
                    "neuroticism": float(p.neuroticism),
                },
            }
        )

    async def api_memories(request: Request) -> JSONResponse:
        q = request.query_params.get("q", "").strip()
        try:
            limit = int(request.query_params.get("limit", "20"))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 200))
        if q:
            results = await soul.recall(q, limit=limit)
        else:
            results = sorted(
                _list_memories(),
                key=lambda m: (-m.importance, -m.created_at.timestamp()),
            )[:limit]
        return _json(
            {"count": len(results), "soul": soul.name, "memories": _memories_payload(results)}
        )

    async def api_stats(request: Request) -> JSONResponse:
        counts = {
            layer: soul._memory.layer(layer).count()
            for layer in ("episodic", "semantic", "procedural", "social")
        }
        counts["total"] = sum(counts.values())
        strength = round(soul.bond.bond_strength, 1)
        return _json(
            {
                "soul": soul.name,
                "memory_counts": counts,
                "interaction_count": soul.bond.interaction_count,
                "bond": {
                    "strength": strength,
                    "bonded_to": soul.bond.bonded_to,
                    "label": _bond_label(strength),
                },
            }
        )

    # ---- New v2 API endpoints ----

    async def api_identity(request: Request) -> JSONResponse:
        ident = soul.identity
        cm = soul.get_core_memory()
        return _json(
            {
                "name": soul.name,
                "did": soul.did,
                "archetype": ident.archetype,
                "born": str(soul.born) if soul.born else None,
                "core_values": list(ident.core_values),
                "persona": cm.persona if cm else "",
                "human": cm.human if cm else "",
                "lifecycle": soul.lifecycle.value,
                "incarnation": ident.incarnation,
            }
        )

    async def api_communication(request: Request) -> JSONResponse:
        comm = soul.dna.communication
        bio = soul.dna.biorhythms
        return _json(
            {
                "warmth": comm.warmth,
                "verbosity": comm.verbosity,
                "humor_style": comm.humor_style,
                "emoji_usage": comm.emoji_usage,
                "biorhythms": {
                    "chronotype": bio.chronotype,
                    "social_battery": bio.social_battery,
                    "mood_inertia": bio.mood_inertia,
                    "mood_sensitivity": bio.mood_sensitivity,
                    "energy_regen_rate": bio.energy_regen_rate,
                },
            }
        )

    async def api_skills(request: Request) -> JSONResponse:
        registry = soul.skills
        return _json(
            {
                "soul": soul.name,
                "skills": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "level": s.level,
                        "xp": s.xp,
                        "xp_to_next": s.xp_to_next,
                        "last_used": str(s.last_used) if s.last_used else None,
                    }
                    for s in registry.skills
                ],
            }
        )

    async def api_evolution(request: Request) -> JSONResponse:
        evo = soul._config.evolution
        return _json(
            {
                "mode": evo.mode.value if hasattr(evo.mode, "value") else str(evo.mode),
                "mutation_rate": evo.mutation_rate,
                "require_approval": evo.require_approval,
                "mutable_traits": list(evo.mutable_traits),
                "immutable_traits": list(evo.immutable_traits),
                "pending": [
                    {
                        "id": m.id,
                        "trait": m.trait,
                        "old_value": m.old_value,
                        "new_value": m.new_value,
                        "reason": m.reason,
                        "proposed_at": str(m.proposed_at) if m.proposed_at else None,
                        "approved": m.approved,
                    }
                    for m in evo.pending
                ],
            }
        )

    async def api_evaluations(request: Request) -> JSONResponse:
        evals = soul._config.evaluation_history
        return _json(
            {
                "soul": soul.name,
                "evaluations": [
                    {
                        "rubric_id": e.get("rubric_id", ""),
                        "overall_score": e.get("overall_score", 0),
                        "learning": e.get("learning", ""),
                        "timestamp": e.get("timestamp", ""),
                    }
                    for e in evals
                ],
            }
        )

    async def api_trust_chain(request: Request) -> JSONResponse:
        tc = soul.trust_chain
        entries = tc.entries if tc else []
        return _json(
            {
                "total": tc.length if tc else 0,
                "entries": [
                    {
                        "seq": e.seq,
                        "action": e.action,
                        "timestamp": str(e.timestamp) if e.timestamp else None,
                        "hash": e.payload_hash,
                        "algorithm": e.algorithm,
                    }
                    for e in entries[:50]
                ],
            }
        )

    async def api_self_model(request: Request) -> JSONResponse:
        sm = soul.self_model
        images = {}
        if sm and sm.self_images:
            for k, v in sm.self_images.items():
                images[k] = {
                    "confidence": v.confidence,
                    "evidence_count": v.evidence_count,
                }
        return _json({"soul": soul.name, "self_images": images})

    async def api_metadata(request: Request) -> JSONResponse:
        cfg = soul._config
        mem_cfg = cfg.memory
        return _json(
            {
                "version": cfg.version,
                "did": soul.did,
                "lifecycle": soul.lifecycle.value,
                "incarnation": soul.identity.incarnation,
                "encrypted": False,
                "memory_config": {
                    "episodic_max_entries": mem_cfg.episodic_max_entries,
                    "semantic_max_facts": mem_cfg.semantic_max_facts,
                    "importance_threshold": mem_cfg.importance_threshold,
                    "consolidation_interval": mem_cfg.consolidation_interval,
                },
            }
        )

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/state", state, methods=["GET"]),
        Route("/remember", remember, methods=["POST"]),
        Route("/recall", recall, methods=["POST"]),
        Route("/observe", observe, methods=["POST"]),
        Route("/turn", turn, methods=["POST"]),
        Route("/v1/chat/completions", chat_completions, methods=["POST"]),
        Route("/dashboard", dashboard, methods=["GET"]),
        Route("/privacy", privacy, methods=["GET"]),
        Route("/terms", terms, methods=["GET"]),
        Route("/favicon.svg", favicon, methods=["GET"]),
        Route("/favicon.ico", favicon, methods=["GET"]),
        Route("/api/personality", api_personality, methods=["GET"]),
        Route("/api/memories", api_memories, methods=["GET"]),
        Route("/api/stats", api_stats, methods=["GET"]),
        Route("/api/identity", api_identity, methods=["GET"]),
        Route("/api/communication", api_communication, methods=["GET"]),
        Route("/api/skills", api_skills, methods=["GET"]),
        Route("/api/evolution", api_evolution, methods=["GET"]),
        Route("/api/evaluations", api_evaluations, methods=["GET"]),
        Route("/api/trust-chain", api_trust_chain, methods=["GET"]),
        Route("/api/self-model", api_self_model, methods=["GET"]),
        Route("/api/metadata", api_metadata, methods=["GET"]),
    ]
    return Starlette(routes=routes, lifespan=lifespan)
