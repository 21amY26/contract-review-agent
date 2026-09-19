from __future__ import annotations

import pytest

from scripts.monitor_pipeline import resolve_contract_path, run_monitoring_pipeline


class TestMonitoringPipeline:
    def test_resolve_contract_path_returns_first_available_sample(self):
        resolved = resolve_contract_path(None)

        assert resolved.exists()
        assert resolved.name == "Sample_Master_Services_Agreement.pdf"

    @pytest.mark.asyncio
    async def test_runs_each_stage_and_updates_state(self):
        calls: list[str] = []

        async def stage_one(state):
            calls.append("one")
            return {"first": 1}

        async def stage_two(state):
            calls.append("two")
            return {"second": 2}

        state = {"contract_id": "demo"}
        outputs = await run_monitoring_pipeline(
            state,
            stages=[("one", stage_one), ("two", stage_two)],
        )

        assert calls == ["one", "two"]
        assert outputs[0][0] == "one"
        assert outputs[0][1] == {"first": 1}
        assert state["first"] == 1
        assert state["second"] == 2
