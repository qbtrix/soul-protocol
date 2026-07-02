# costmeter.py — Cost meter + replay cache at the `generate` seam of the
#   npc.soul grudge kernel.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Two SMALL composable
#   wrappers around the async `generate(prompt) -> str` callable that backs
#   LLMDialogueEngine. ZERO changes to grudge.py / dialogue.py / player.py —
#   pure seam composition:
#
#     * CostMeter(generate, model=...) — awaitable passthrough that records, per
#       call: estimated tokens in (len(prompt)//4), estimated tokens out
#       (len(reply)//4), latency seconds, and $ cost from PRICING ($ per 1M
#       tokens). summary() rolls the session up (calls, tokens, total_cost,
#       avg_latency, cost_per_100_lines projection);
#       cost_per_player_hour(lines_per_hour=90) prices an hour of play; and
#       project(model) re-prices the SAME recorded traffic under another
#       model's rates ("what would this session cost on deepseek-v3.2?").
#       When the inner callable is a ReplayCache, cache HITS are detected (the
#       cache's `hits` counter advanced during the call) and counted as FREE
#       (`cached_calls`) — no tokens, no $ — so only real model calls are
#       metered.
#
#     * ReplayCache(generate, path=...) — content-addressed cache keyed by
#       sha256(prompt). HIT: return the stored reply WITHOUT calling generate.
#       MISS: call generate, store, append {"key","prompt","reply"} to the
#       jsonl at `path`. An existing jsonl is loaded at init (`load()` is the
#       explicit classmethod spelling of the same thing), so a REPLAYED session
#       is deterministic AND zero-LLM-cost — the machine-decidable gate: same
#       player lines -> byte-identical NPC lines, zero generate calls, $0.
#
#   They compose: LLMDialogueEngine(CostMeter(ReplayCache(generate, path),
#   model=...)) — the engine still sees one async callable, unchanged.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — GRADUATED from
#   examples/npc_soul_grudge/ into soul_protocol.profiles.game (git mv, history
#   preserved). No code changes — the module has no sibling imports.
#   Spec: spec/profiles/game.md.

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

# $ per 1M tokens as (input_rate, output_rate). claude-cli (local, no key) and
# gemini-nano (on-device) are $0 — the meter still counts their tokens so
# project() can re-price the same session under a paid model.
PRICING: dict[str, tuple[float, float]] = {
    "deepseek-v3.2": (0.14, 0.28),
    "gemini-flash-lite": (0.10, 0.40),
    "gemini-nano": (0.0, 0.0),
    "claude-cli": (0.0, 0.0),
}


def _estimate_tokens(text: str) -> int:
    """Cheap, model-free token estimate: ~4 chars per token."""
    return len(text) // 4


class CostMeter:
    """Awaitable passthrough that meters an async ``generate(prompt) -> str``.

    ``meter = CostMeter(generate, model="deepseek-v3.2")`` — then use ``meter``
    anywhere the raw callable went: ``await meter(prompt)``. Per non-cached call
    it records estimated tokens in/out, latency, and $ cost from PRICING.
    """

    def __init__(self, generate, model: str = "claude-cli") -> None:
        if model not in PRICING:
            raise ValueError(f"unknown model {model!r}; expected one of {sorted(PRICING)}")
        self._generate = generate
        self.model = model
        self.calls = 0  # metered (real model) calls
        self.cached_calls = 0  # calls served free by an inner ReplayCache
        self.tokens_in = 0
        self.tokens_out = 0
        self.total_cost = 0.0
        self.total_latency = 0.0

    async def __call__(self, prompt: str) -> str:
        inner = self._generate
        hits_before = getattr(inner, "hits", None)
        start = time.monotonic()
        reply = await inner(prompt)
        latency = time.monotonic() - start

        if hits_before is not None and getattr(inner, "hits", hits_before) > hits_before:
            # Served from a ReplayCache — no model ran, so nothing to meter.
            self.cached_calls += 1
            return reply

        tokens_in = _estimate_tokens(prompt)
        tokens_out = _estimate_tokens(reply)
        in_rate, out_rate = PRICING[self.model]
        self.calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.total_latency += latency
        self.total_cost += (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
        return reply

    def summary(self) -> dict:
        """Session roll-up, including the per-100-lines cost projection."""
        avg_latency = self.total_latency / self.calls if self.calls else 0.0
        per_line = self.total_cost / self.calls if self.calls else 0.0
        return {
            "model": self.model,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "total_cost": self.total_cost,
            "avg_latency": avg_latency,
            "cost_per_100_lines": per_line * 100,
        }

    def cost_per_player_hour(self, lines_per_hour: int = 90) -> float:
        """Project the metered per-line cost onto an hour of play."""
        if not self.calls:
            return 0.0
        return (self.total_cost / self.calls) * lines_per_hour

    def project(self, model: str) -> float:
        """What the SAME recorded traffic would cost under another model."""
        if model not in PRICING:
            raise ValueError(f"unknown model {model!r}; expected one of {sorted(PRICING)}")
        in_rate, out_rate = PRICING[model]
        return (self.tokens_in * in_rate + self.tokens_out * out_rate) / 1_000_000


class ReplayCache:
    """Content-addressed cache over an async ``generate(prompt) -> str``.

    Key = sha256(prompt). Hit: return the stored reply WITHOUT calling the
    inner generate. Miss: call, store in memory, append one JSON line
    ({"key","prompt","reply"}) to the jsonl at ``path``. If the file already
    exists it is loaded at construction, which is what makes a REPLAYED session
    deterministic and zero-LLM-cost.
    """

    def __init__(self, generate, path: str | Path) -> None:
        self._generate = generate
        self.path = Path(path)
        self.hits = 0
        self.misses = 0
        self._cache: dict[str, str] = {}
        if self.path.exists():
            for raw in self.path.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                self._cache[record["key"]] = record["reply"]

    @classmethod
    def load(cls, generate, path: str | Path) -> ReplayCache:
        """Explicit spelling of init-from-existing-jsonl (init already loads)."""
        return cls(generate, path)

    def __len__(self) -> int:
        return len(self._cache)

    @staticmethod
    def _key(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def __call__(self, prompt: str) -> str:
        key = self._key(prompt)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        reply = await self._generate(prompt)
        self._cache[key] = reply
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "prompt": prompt, "reply": reply}) + "\n")
        return reply
