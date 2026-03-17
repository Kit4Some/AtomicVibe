"""Unit tests for CostTracker."""

from __future__ import annotations

import pytest

from architect.llm.cost_tracker import CostTracker, _compute_cost


# ---------------------------------------------------------------------------
# _compute_cost fallback
# ---------------------------------------------------------------------------


class TestComputeCost:
    def test_compute_cost_uses_price_table(self) -> None:
        cost = _compute_cost("claude-sonnet-4.6", input_tokens=1000, output_tokens=500)
        # (1000 * 0.003 + 500 * 0.015) / 1000 = 0.003 + 0.0075 = 0.0105
        assert cost == pytest.approx(0.0105)

    def test_compute_cost_unknown_model_returns_zero(self) -> None:
        cost = _compute_cost("unknown/model", input_tokens=100, output_tokens=50)
        assert cost == 0.0


# ---------------------------------------------------------------------------
# CostTracker
# ---------------------------------------------------------------------------


class TestCostTracker:
    @pytest.fixture()
    def tracker(self) -> CostTracker:
        return CostTracker()

    @pytest.mark.asyncio()
    async def test_track_accumulates_cost(self, tracker: CostTracker) -> None:
        await tracker.track("claude-sonnet-4.6", 1000, 500, "plan_analysis")
        await tracker.track("claude-sonnet-4.6", 1000, 500, "code_generation")
        total = await tracker.get_total_cost()
        assert total == pytest.approx(0.0105 * 2)

    @pytest.mark.asyncio()
    async def test_get_total_cost_returns_sum(self, tracker: CostTracker) -> None:
        await tracker.track("claude-haiku-4.5", 2000, 1000, "supervisor")
        # (2000 * 0.001 + 1000 * 0.005) / 1000 = 0.002 + 0.005 = 0.007
        total = await tracker.get_total_cost()
        assert total == pytest.approx(0.007)

    @pytest.mark.asyncio()
    async def test_check_budget_within_limit(self, tracker: CostTracker) -> None:
        await tracker.track("claude-sonnet-4.6", 1000, 500, "fix")
        assert tracker.check_budget(1.0) is True

    @pytest.mark.asyncio()
    async def test_check_budget_exceeded(self, tracker: CostTracker) -> None:
        await tracker.track("claude-sonnet-4.6", 1000, 500, "fix")
        assert tracker.check_budget(0.001) is False

    @pytest.mark.asyncio()
    async def test_get_usage_report_groups_by_model_and_purpose(
        self, tracker: CostTracker,
    ) -> None:
        await tracker.track("claude-sonnet-4.6", 100, 50, "plan_analysis")
        await tracker.track("claude-haiku-4.5", 200, 100, "supervisor")

        report = await tracker.get_usage_report()

        assert report["total_calls"] == 2
        assert "claude-sonnet-4.6" in report["by_model"]  # type: ignore[operator]
        assert "claude-haiku-4.5" in report["by_model"]  # type: ignore[operator]
        assert "plan_analysis" in report["by_purpose"]  # type: ignore[operator]
        assert "supervisor" in report["by_purpose"]  # type: ignore[operator]
