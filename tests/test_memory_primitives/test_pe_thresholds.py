# test_pe_thresholds.py — Exhaustive PE-vs-verb matrix.
# Created: 2026-04-29 (#192) — verifies the PE band check for every verb that
# enforces one. The bands are locked at confirm <0.2, update [0.2, 0.85),
# supersede >=0.85.

from __future__ import annotations

import pytest

from soul_protocol.runtime.exceptions import PredictionErrorOutOfBandError


class TestUpdateBands:
    @pytest.mark.parametrize("pe", [0.2, 0.5, 0.84])
    @pytest.mark.asyncio
    async def test_update_inside_band(self, soul_with_facts, pe):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        result = await soul.update(mid, "patch", prediction_error=pe)
        assert result["found"] is True

    @pytest.mark.parametrize("pe", [0.0, 0.05, 0.19])
    @pytest.mark.asyncio
    async def test_update_below_band(self, soul_with_facts, pe):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.update(mid, "patch", prediction_error=pe)

    @pytest.mark.parametrize("pe", [0.85, 0.9, 1.0])
    @pytest.mark.asyncio
    async def test_update_above_band(self, soul_with_facts, pe):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.update(mid, "patch", prediction_error=pe)


class TestSupersedeBands:
    @pytest.mark.parametrize("pe", [0.85, 0.9, 1.0])
    @pytest.mark.asyncio
    async def test_supersede_inside_band(self, soul_with_facts, pe):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        result = await soul.supersede(old_id, "new", prediction_error=pe)
        assert result["found"] is True

    @pytest.mark.parametrize("pe", [0.0, 0.5, 0.84])
    @pytest.mark.asyncio
    async def test_supersede_below_band(self, soul_with_facts, pe):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.supersede(old_id, "new", prediction_error=pe)
