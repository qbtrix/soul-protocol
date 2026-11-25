# test_decide/test_nli_live.py — Live accuracy check for NLIContradictionDecider.
# Created: feat/soul-instinct — Runs the real cross-encoder and embedding models on
#   a small hand-labelled set, including the SNLI failure modes (unrelated facts
#   judged as contradictions) and first-person phrasing. Opt-in because it
#   downloads ~100 MB of models:
#     pip install 'soul-protocol[embeddings-st]'
#     SOUL_LIVE_MODELS=1 pytest tests/test_decide/test_nli_live.py

from __future__ import annotations

import os

import pytest

pytest.importorskip("sentence_transformers", reason="needs soul-protocol[embeddings-st]")
if not os.environ.get("SOUL_LIVE_MODELS"):
    pytest.skip("set SOUL_LIVE_MODELS=1 to run live model tests", allow_module_level=True)

from soul_protocol.runtime.decide import (  # noqa: E402
    ContradictionRequest,
    NLIContradictionDecider,
)
from soul_protocol.runtime.soul import Soul  # noqa: E402
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType  # noqa: E402

MEMORIES = [
    MemoryEntry(id=mem_id, type=MemoryType.SEMANTIC, content=content)
    for mem_id, content in [
        ("steak", "User loves steak"),
        ("delhi", "User lives in Delhi"),
        ("google", "User works at Google"),
        ("coffee", "User hates coffee"),
        ("dog", "User has a dog named Bruno"),
    ]
]

CASES = [
    ("User is vegetarian now", {"steak"}),
    ("I'm vegetarian now", {"steak"}),
    ("User moved to Mumbai last month", {"delhi"}),
    ("I moved to Mumbai last month", {"delhi"}),
    ("User got promoted at Google", set()),
    ("User drinks coffee every morning", {"coffee"}),
    ("User likes cricket", set()),
    ("User quit Google", {"google"}),
    ("User adopted a cat", set()),
    ("User left Delhi and lives in Pune now", {"delhi"}),
    ("User no longer eats meat", {"steak"}),
    ("User's dog Bruno turned 5", set()),
    ("User started learning guitar", set()),
]


@pytest.fixture(scope="module")
def decider() -> NLIContradictionDecider:
    return NLIContradictionDecider()


@pytest.mark.parametrize(("text", "expected"), CASES)
async def test_live_contradiction(decider, text, expected):
    decision = await decider.decide(ContradictionRequest(new_content=text, existing=MEMORIES))
    assert {f.old_memory_id for f in decision.value.findings} == expected


async def test_live_soul_catches_what_rules_miss(decider):
    soul = await Soul.birth("Live", deciders=[decider])
    steak = await soul.remember("User loves steak")
    dog = await soul.remember("User has a dog named Bruno")
    for message in ["I like cricket", "I adopted a cat", "I'm vegetarian now"]:
        await soul.observe(Interaction.from_pair(message, "ok"))
    live = {f.id for f in soul._memory.semantic_facts()}
    assert steak not in live
    assert dog in live
