# tests/test_gateway/test_proxy.py - OpenAI-compatible LLM proxy.
# Created: 2026-05 - Verifies POST /v1/chat/completions auto-recalls memories,
#   injects them into the system prompt, forwards to the upstream LLM (mocked),
#   and auto-observes the turn - no manual soul_recall/soul_observe calls.

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("starlette", reason="starlette required for gateway tests")
pytest.importorskip("httpx", reason="httpx required for gateway tests")

import httpx  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from soul_protocol.gateway import create_app  # noqa: E402
from soul_protocol.gateway.app import LLMProxyConfig  # noqa: E402
from soul_protocol.runtime.soul import Soul  # noqa: E402
from soul_protocol.runtime.types import MemoryEntry, MemoryType  # noqa: E402


@pytest.fixture
def proxy():
    soul = asyncio.run(Soul.birth(name="Proxy", archetype="proxy test"))
    asyncio.run(
        soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content="The user's favorite language is Python",
                importance=8,
                domain="default",
            )
        )
    )

    captured: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "You like Python!"}}
                ],
            },
        )

    llm_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = LLMProxyConfig(base_url="http://llm.test/v1", api_key="sk-test", model="gpt-4")
    app = create_app(soul, llm_config=config, llm_client=llm_client, observe_mode="await")
    yield app, llm_client, soul, captured
    asyncio.run(llm_client.aclose())


def test_proxy_returns_llm_response(proxy):
    app, _, _, _ = proxy
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "What language do I love?"}]},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "You like Python!"


def test_proxy_injects_memories_into_system_prompt(proxy):
    app, _, _, captured = proxy
    with TestClient(app) as client:
        client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "What language do I love?"}]},
        )
    body = captured["body"]
    assert body["messages"][0]["role"] == "system"
    assert "Python" in body["messages"][0]["content"]
    assert body["model"] == "gpt-4"


def test_proxy_auto_observes_turn(proxy):
    app, _, soul, _ = proxy
    calls: list[tuple[str, str]] = []

    async def spy_observe(interaction, *, user_id=None, domain="default"):
        calls.append((interaction.user_input, interaction.agent_output))

    soul.observe = spy_observe  # type: ignore[method-assign]
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "What language do I love?"}]},
        )
    assert r.status_code == 200
    assert calls == [("What language do I love?", "You like Python!")]


def test_proxy_fire_and_forget_mode_returns_response(proxy):
    _, llm_client, soul, _ = proxy
    config = LLMProxyConfig(base_url="http://llm.test/v1", api_key="sk-test", model="gpt-4")
    app = create_app(soul, llm_config=config, llm_client=llm_client, observe_mode="fire_and_forget")
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "You like Python!"


def test_proxy_validation_errors(proxy):
    app, _, _, _ = proxy
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json={}).status_code == 400
        assert (
            client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
            ).status_code
            == 400
        )
