# test_decide/test_soul_instinct.py — End-to-end Soul Instinct tests through the Soul API.
# Created: feat/soul-instinct — observe() routed through deciders, uncertain-memory
#   marking, crash/abstain fallbacks, review_instincts() restoring and applying
#   contradictions, calibration learning, persistence through export/awaken, the
#   dream() review hook, personality modulation, and the read-only decide() API.
# Updated: feat/soul-instinct (#322 review) — A confident "no contradiction" no
#   longer switches the rules off (the reviewer's steak repro); rule-only
#   supersedes are left uncertain. Review restores the memory's original
#   confidence instead of writing the reviewer's. observe() reports only the
#   uncertain markers it stamped.

from __future__ import annotations

import json

import pytest

from soul_protocol.runtime.memory.manager import INSTINCT_METADATA_KEY
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemoryEntry
from tests.test_decide.conftest import (
    FixedSignificanceDecider,
    KeywordContradictionDecider,
    ScriptedEngine,
)


def _fact(soul: Soul, memory_id: str) -> MemoryEntry:
    return next(
        f for f in soul._memory.semantic_facts(include_superseded=True) if f.id == memory_id
    )


def _snapshot(soul: Soul) -> list[tuple]:
    entries = soul._memory.episodic_entries() + soul._memory.semantic_facts(include_superseded=True)
    return sorted(
        (e.type, e.content, e.superseded, e.superseded_by is not None, e.importance)
        for e in entries
    )


def _reviewer(contradicted: bool, confidence: float = 0.9) -> ScriptedEngine:
    """LLM stand-in: answers review prompts, returns junk JSON for everything else."""

    def reply(prompt: str) -> str:
        if "Decide which OLD memories" in prompt:
            return json.dumps(
                {"contradicted": [1] if contradicted else [], "confidence": confidence}
            )
        return "{}"

    return ScriptedEngine(reply)


CONVERSATION = [
    ("I love steak", "Nice!"),
    ("My name is Arjun and I work at Stripe", "Great to meet you, Arjun"),
    ("I'm vegetarian now", "Got it!"),
    ("hi", "hello"),
]


class TestObservePipeline:
    async def test_no_deciders_no_markers(self):
        soul = await Soul.birth("Plain")
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "Got it!"))
        assert soul.deciders == []
        assert soul.uncertain_memories() == []
        assert soul._memory.instinct_entries(uncertain_only=False) == []

    async def test_abstaining_decider_matches_plain_soul(self):
        """Attaching deciders that never answer must not change any memory."""

        class Silent:
            name = "silent"

            def supports(self, kind):
                return True

            async def decide(self, request):
                return None

        plain = await Soul.birth("Plain")
        silent = await Soul.birth("Plain", deciders=[Silent()])
        for soul in (plain, silent):
            await soul.remember("User loves steak")
            for user, agent in CONVERSATION:
                await soul.observe(Interaction.from_pair(user, agent))
        assert _snapshot(plain) == _snapshot(silent)

    async def test_confident_decider_catches_what_rules_miss(self):
        plain = await Soul.birth("Plain")
        smart = await Soul.birth("Smart", deciders=[KeywordContradictionDecider(confidence=0.95)])
        ids = {}
        for soul in (plain, smart):
            ids[soul.name] = await soul.remember("User loves steak")
            await soul.observe(Interaction.from_pair("I'm vegetarian now", "Got it!"))

        assert not _fact(plain, ids["Plain"]).superseded  # the known heuristic gap
        steak = _fact(smart, ids["Smart"])
        assert steak.superseded
        marker = steak.metadata[INSTINCT_METADATA_KEY]
        assert marker["source"] == "keyword"
        assert marker["uncertain"] is False
        assert smart.uncertain_memories() == []

    async def test_unsure_decider_marks_memory_for_review(self):
        soul = await Soul.birth("Unsure", deciders=[KeywordContradictionDecider(confidence=0.4)])
        steak_id = await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "Got it!"))

        steak = _fact(soul, steak_id)
        assert not steak.superseded  # fallback (rules) decided: no contradiction
        assert steak.confidence == pytest.approx(0.4)
        marker = steak.metadata[INSTINCT_METADATA_KEY]
        assert marker["uncertain"] is True
        assert marker["model_verdict"] is True
        assert marker["applied"] is False
        assert [e.id for e in soul.uncertain_memories()] == [steak_id]

    async def test_confident_no_contradiction_keeps_rule_supersede(self):
        """Reviewer's repro: rules alone supersede "loves steak" on "dislikes steak".

        A decider that confidently answers "nothing contradicts" must not turn
        that off, and the disagreement must be left for review.
        """
        plain = await Soul.birth("Plain")
        blind = KeywordContradictionDecider("blind", confidence=1.0, trigger="no-such-trigger")
        smart = await Soul.birth("Smart", deciders=[blind])
        ids = {}
        for soul in (plain, smart):
            ids[soul.name] = await soul.remember("User loves steak")
            await soul.observe(Interaction.from_pair("User dislikes steak", "Noted"))

        assert _fact(plain, ids["Plain"]).superseded
        steak = _fact(smart, ids["Smart"])
        assert steak.superseded
        assert blind.calls > 0
        marker = steak.metadata[INSTINCT_METADATA_KEY]
        assert marker["source"] == "blind"
        assert marker["uncertain"] is True
        assert marker["model_verdict"] is False
        assert marker["applied"] is True
        assert [e.id for e in smart.uncertain_memories()] == [steak.id]

    async def test_observe_reports_uncertain_marked_in_this_call(self):
        soul = await Soul.birth("Count", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        first = await soul._memory.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        second = await soul._memory.observe(Interaction.from_pair("Nice weather", "Yes"))
        assert first["instinct"]["uncertain"] == 1
        assert second["instinct"]["uncertain"] == 0  # not a running total
        assert len(soul.uncertain_memories()) == 1

    async def test_crashing_decider_never_breaks_observe(self):
        broken = KeywordContradictionDecider(error=ConnectionError("API down"))
        soul = await Soul.birth("Resilient", deciders=[broken])
        await soul.remember("User loves steak")
        for user, agent in CONVERSATION:
            await soul.observe(Interaction.from_pair(user, agent))
        assert broken.calls > 0
        assert soul.uncertain_memories() == []

    async def test_significance_decider_gates_episodic_storage(self):
        keep = await Soul.birth("Keep", deciders=[FixedSignificanceDecider(significant=True)])
        drop = await Soul.birth("Drop", deciders=[FixedSignificanceDecider(significant=False)])
        for soul in (keep, drop):
            await soul.observe(Interaction.from_pair("hi", "hello"))
        assert len(keep._memory.episodic_entries()) == 1
        assert len(drop._memory.episodic_entries()) == 0
        episode = keep._memory.episodic_entries()[0]
        assert episode.metadata[INSTINCT_METADATA_KEY]["source"] == "fixed-sig"

    async def test_use_deciders_attach_and_detach(self):
        soul = await Soul.birth("Toggle")
        decider = KeywordContradictionDecider()
        soul.use_deciders([decider])
        assert soul.deciders == [decider]
        soul.use_deciders([])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        assert decider.calls == 0


class TestReview:
    async def test_review_applies_missed_contradiction_and_learns(self):
        soul = await Soul.birth("Learner", deciders=[KeywordContradictionDecider(confidence=0.4)])
        steak_id = await soul.remember("User loves steak")
        _fact(soul, steak_id).confidence = 0.8
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "Got it!"))
        marker = _fact(soul, steak_id).metadata[INSTINCT_METADATA_KEY]
        assert _fact(soul, steak_id).confidence == pytest.approx(0.4)
        assert marker["original_confidence"] == 0.8

        report = await soul.review_instincts(
            reviewer=_reviewer_decider(contradicted=True, confidence=0.92)
        )

        assert (report.reviewed, report.corrected, report.superseded) == (1, 1, 1)
        steak = _fact(soul, steak_id)
        assert steak.superseded
        # The memory's own confidence comes back; the reviewer's stays in the marker.
        assert steak.confidence == 0.8
        assert steak.metadata[INSTINCT_METADATA_KEY]["uncertain"] is False
        assert steak.metadata[INSTINCT_METADATA_KEY]["reviewed"]["by"] == "llm"
        assert steak.metadata[INSTINCT_METADATA_KEY]["reviewed"]["confidence"] == 0.92
        assert soul.uncertain_memories() == []
        # The unsure model was right → its 0.4-band answers are trusted more.
        cal = soul.instinct.calibration
        assert cal.accuracy("keyword", "contradiction") == 1.0
        assert cal.calibrate("keyword", "contradiction", 0.4) > 0.4

    async def test_review_restores_wrongly_superseded_memory(self):
        unsure = KeywordContradictionDecider(confidence=0.4, trigger="dislikes")
        soul = await Soul.birth("Restorer", deciders=[unsure])
        steak_id = await soul.remember("User loves steak")
        # The rules' negation check supersedes this; the model was unsure.
        await soul.observe(Interaction.from_pair("User dislikes steak", "Noted"))
        assert _fact(soul, steak_id).superseded

        report = await soul.review_instincts(reviewer=_reviewer_decider(contradicted=False))

        assert report.restored == 1
        restored = _fact(soul, steak_id)
        assert not restored.superseded
        assert restored.superseded_by is None
        assert (
            restored.confidence == restored.metadata[INSTINCT_METADATA_KEY]["original_confidence"]
        )
        # The model said "contradiction" and the reviewer disagreed → wrong.
        assert soul.instinct.calibration.accuracy("keyword", "contradiction") == 0.0

    async def test_review_without_engine_is_a_noop(self):
        soul = await Soul.birth("NoEngine", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        report = await soul.review_instincts()
        assert report.reviewed == 0
        assert "no reviewer" in report.note
        assert len(soul.uncertain_memories()) == 1

    async def test_reviewer_errors_are_counted_not_raised(self):
        soul = await Soul.birth("Flaky", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        from soul_protocol.runtime.decide import EngineDecider

        report = await soul.review_instincts(
            reviewer=EngineDecider(ScriptedEngine(lambda p: "not json at all"))
        )
        assert report.errors == 1
        assert len(soul.uncertain_memories()) == 1

    async def test_dream_runs_review_with_engine(self):
        soul = await Soul.birth("Dreamer", deciders=[KeywordContradictionDecider(confidence=0.4)])
        steak_id = await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        soul.set_engine(_reviewer(contradicted=True))

        report = await soul.dream()

        assert report.instinct_reviewed == 1
        assert report.instinct_corrected == 1
        assert "Instinct decisions reviewed: 1" in report.summary()
        assert _fact(soul, steak_id).superseded

    async def test_dream_review_can_be_disabled(self):
        soul = await Soul.birth("Lazy", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        soul.set_engine(_reviewer(contradicted=True))
        soul.instinct.settings.review_during_dream = False

        assert (await soul.dream()).instinct_reviewed == 0
        assert (await soul.dream(review_instincts=True)).instinct_reviewed == 1

    async def test_dry_run_dream_never_reviews(self):
        soul = await Soul.birth("Dry", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        soul.set_engine(_reviewer(contradicted=True))
        assert (await soul.dream(dry_run=True)).instinct_reviewed == 0
        assert len(soul.uncertain_memories()) == 1


class TestPersistence:
    async def test_calibration_and_markers_survive_export(self, tmp_path):
        soul = await Soul.birth("Portable", deciders=[KeywordContradictionDecider(confidence=0.4)])
        await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        soul.instinct.settings.min_confidence = 0.8
        soul.instinct.calibration.record("nli", "contradiction", 0.9, correct=True)
        path = tmp_path / "portable.soul"
        await soul.export(str(path))

        reloaded = await Soul.awaken(str(path))

        assert reloaded.deciders == []  # deciders are runtime-only
        assert reloaded.instinct.settings.min_confidence == 0.8
        assert reloaded.instinct.calibration.accuracy("nli", "contradiction") == 1.0
        assert len(reloaded.uncertain_memories()) == 1
        # Calibration learned after awaken is still saved with the soul.
        reloaded.instinct.calibration.record("nli", "contradiction", 0.9, correct=False)
        assert reloaded.serialize().instinct.calibration.accuracy("nli", "contradiction") == 0.5

    async def test_awaken_attaches_deciders_to_restored_memory(self, tmp_path):
        soul = await Soul.birth("Again")
        steak_id = await soul.remember("User loves steak")
        path = tmp_path / "again.soul"
        await soul.export(str(path))

        reloaded = await Soul.awaken(str(path), deciders=[KeywordContradictionDecider()])
        await reloaded.observe(Interaction.from_pair("I'm vegetarian now", "ok"))

        assert _fact(reloaded, steak_id).superseded

    async def test_reincarnation_keeps_instinct(self):
        decider = KeywordContradictionDecider()
        old = await Soul.birth("Phoenix", deciders=[decider])
        old.instinct.calibration.record("nli", "contradiction", 0.9, correct=True)
        old.instinct.settings.min_confidence = 0.85

        new = await Soul.reincarnate(old)

        assert new.instinct.calibration.accuracy("nli", "contradiction") == 1.0
        assert new.instinct.settings.min_confidence == 0.85
        assert new.deciders == [decider]
        assert new.instinct is not old.instinct  # independent copy

    async def test_legacy_config_without_instinct_loads(self):
        from soul_protocol.runtime.types import SoulConfig

        config = SoulConfig.model_validate({"identity": {"name": "Old"}})
        assert config.instinct.settings.min_confidence == 0.7


class TestPersonalityAndSettings:
    async def test_modulation_is_opt_in(self):
        soul = await Soul.birth("Careful", ocean={"conscientiousness": 1.0, "openness": 1.0})
        chain, _ = soul._memory._decision_chains()
        assert chain.min_confidence == 0.7

        soul.instinct.settings.personality_modulation = True
        chain, raw = soul._memory._decision_chains()
        assert chain.min_confidence == pytest.approx(0.8)
        assert raw.fallback._significance_threshold == pytest.approx(0.25)

    async def test_min_confidence_setting_gates_answers(self):
        soul = await Soul.birth("Strict", deciders=[KeywordContradictionDecider(confidence=0.8)])
        soul.instinct.settings.min_confidence = 0.9
        steak_id = await soul.remember("User loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        assert not _fact(soul, steak_id).superseded
        assert len(soul.uncertain_memories()) == 1


class TestDecideApi:
    async def test_decide_is_read_only(self):
        soul = await Soul.birth("Asker", deciders=[KeywordContradictionDecider()])
        steak_id = await soul.remember("User loves steak")

        decision = await soul.decide("contradiction", "I'm vegetarian now")

        assert decision.source == "keyword"
        assert [f.old_memory_id for f in decision.value.findings] == [steak_id]
        assert not _fact(soul, steak_id).superseded

    @pytest.mark.parametrize("kind", ["sentiment", "significance", "contradiction", "dedup"])
    async def test_every_kind_answers_without_deciders(self, kind):
        soul = await Soul.birth("Basic")
        await soul.remember("User loves steak")
        decision = await soul.decide(kind, "User loves steak")
        assert decision.kind == kind
        assert decision.source == "cognitive"

    async def test_dedup_recognizes_known_fact(self):
        soul = await Soul.birth("Dedup")
        steak_id = await soul.remember("User loves steak")
        decision = await soul.decide("dedup", "User loves steak")
        assert decision.value.action == "SKIP"
        assert decision.value.target_id == steak_id

    async def test_unknown_kind_raises(self):
        soul = await Soul.birth("Bad")
        with pytest.raises(ValueError):
            await soul.decide("telepathy", "hello")


def _reviewer_decider(contradicted: bool, confidence: float = 0.9):
    from soul_protocol.runtime.decide import EngineDecider

    return EngineDecider(_reviewer(contradicted, confidence))


class TestUserAliases:
    async def test_aliases_reach_deciders_and_persist(self, tmp_path):
        seen: list[list[str]] = []

        class Recorder(KeywordContradictionDecider):
            async def decide(self, request):
                seen.append(list(getattr(request, "user_aliases", [])))
                return await super().decide(request)

        soul = await Soul.birth("Shekhar", deciders=[Recorder()])
        soul.instinct.settings.user_aliases = ["Shekhar"]
        await soul.remember("Shekhar loves steak")
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        await soul.decide("contradiction", "I'm vegetarian now")

        assert seen and all(a == ["Shekhar"] for a in seen)
        path = tmp_path / "alias.soul"
        await soul.export(str(path))
        assert (await Soul.awaken(str(path))).instinct.settings.user_aliases == ["Shekhar"]


class TestOriginalConfidence:
    def _manager_and_entry(self, confidence: float):
        from soul_protocol.runtime.memory.manager import MemoryManager
        from soul_protocol.runtime.types import CoreMemory, MemorySettings, MemoryType

        manager = MemoryManager(core=CoreMemory(), settings=MemorySettings())
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="User loves steak")
        entry.confidence = confidence
        return manager, entry

    def test_second_marker_keeps_first_original(self):
        manager, entry = self._manager_and_entry(0.9)
        manager._stamp_instinct(entry, {"uncertain": True, "confidence": 0.5})
        manager._stamp_instinct(entry, {"uncertain": True, "confidence": 0.3})
        assert entry.confidence == 0.3
        assert entry.metadata[INSTINCT_METADATA_KEY]["original_confidence"] == 0.9

    def test_confident_marker_leaves_confidence_alone(self):
        manager, entry = self._manager_and_entry(0.9)
        manager._stamp_instinct(entry, {"uncertain": False, "confidence": 0.2})
        assert entry.confidence == 0.9
        assert entry.metadata[INSTINCT_METADATA_KEY]["original_confidence"] == 0.9
