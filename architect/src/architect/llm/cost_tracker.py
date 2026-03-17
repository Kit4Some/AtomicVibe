"""Cost tracking and budget enforcement for LLM calls."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from architect.llm.models import MODEL_PRICES

_log = logging.getLogger("architect.llm.cost_tracker")


@dataclass(slots=True)
class _UsageRecord:
    """Single LLM call usage record."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    purpose: str


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in USD from the internal price table."""
    prices = MODEL_PRICES.get(model)
    if prices is None:
        _log.warning("No pricing info for model %s, assuming zero cost", model)
        return 0.0
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1000.0


class CostTracker:
    """Thread-safe LLM cost tracker with budget enforcement."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._records: list[_UsageRecord] = []
        self._total_cost: float = 0.0
        self._by_model: dict[str, float] = defaultdict(float)
        self._by_purpose: dict[str, float] = defaultdict(float)
        self._tokens_by_model: dict[str, dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0},
        )

    async def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str,
    ) -> None:
        """Record a single LLM call's usage and cost."""
        cost = _compute_cost(model, input_tokens, output_tokens)
        record = _UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            purpose=purpose,
        )
        async with self._lock:
            self._records.append(record)
            self._total_cost += cost
            self._by_model[model] += cost
            self._by_purpose[purpose] += cost
            self._tokens_by_model[model]["input"] += input_tokens
            self._tokens_by_model[model]["output"] += output_tokens

        _log.debug(
            "LLM call tracked: model=%s purpose=%s in=%d out=%d cost=%.6f total=%.6f",
            model, purpose, input_tokens, output_tokens,
            round(cost, 6), round(self._total_cost, 6),
        )

    async def get_total_cost(self) -> float:
        """Return the total accumulated cost in USD."""
        async with self._lock:
            return self._total_cost

    def check_budget(self, max_cost_usd: float) -> bool:
        """Return ``True`` if spending is within the budget limit."""
        return self._total_cost <= max_cost_usd

    async def get_usage_report(self) -> dict[str, object]:
        """Return a summary of usage grouped by model and purpose."""
        async with self._lock:
            return {
                "total_cost_usd": round(self._total_cost, 6),
                "total_calls": len(self._records),
                "by_model": {
                    model: {
                        "cost_usd": round(cost, 6),
                        "input_tokens": self._tokens_by_model[model]["input"],
                        "output_tokens": self._tokens_by_model[model]["output"],
                    }
                    for model, cost in self._by_model.items()
                },
                "by_purpose": {
                    purpose: round(cost, 6)
                    for purpose, cost in self._by_purpose.items()
                },
            }
