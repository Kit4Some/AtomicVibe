"""Unit tests for the analyze_request node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from architect.core.models import DomainAnalysis
from architect.plan.nodes.analyze import make_analyze_node
from architect.plan.states import STEP_CHOICES, create_initial_state


def _mock_domain_analysis() -> DomainAnalysis:
    return DomainAnalysis(
        domain="E-commerce",
        project_type="Full Stack",
        core_features=["Product catalog", "Shopping cart", "Checkout"],
        implied_requirements=["Authentication", "Payment integration"],
        complexity="medium",
        estimated_agents=4,
        initial_questions=["What payment providers?", "Need admin panel?"],
    )


def _make_mock_router(analysis: DomainAnalysis) -> MagicMock:
    router = MagicMock()
    router.complete_structured = AsyncMock(return_value=analysis)
    return router


@pytest.mark.asyncio
async def test_analyze_request_extracts_domain_analysis() -> None:
    analysis = _mock_domain_analysis()
    router = _make_mock_router(analysis)
    node = make_analyze_node(router)

    state = create_initial_state("Build an e-commerce platform")
    result = await node(state)

    assert result["domain_analysis"]["domain"] == "E-commerce"
    assert result["domain_analysis"]["project_type"] == "Full Stack"
    assert result["domain_analysis"]["complexity"] == "medium"
    router.complete_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_request_sets_open_questions() -> None:
    analysis = _mock_domain_analysis()
    router = _make_mock_router(analysis)
    node = make_analyze_node(router)

    state = create_initial_state("Build an e-commerce platform")
    result = await node(state)

    assert len(result["open_questions"]) == 2
    assert "What payment providers?" in result["open_questions"]


@pytest.mark.asyncio
async def test_analyze_request_adds_to_conversation_history() -> None:
    analysis = _mock_domain_analysis()
    router = _make_mock_router(analysis)
    node = make_analyze_node(router)

    state = create_initial_state("Build an e-commerce platform")
    result = await node(state)

    assert len(result["conversation_history"]) == 1
    msg = result["conversation_history"][0]
    assert msg["role"] == "assistant"
    assert msg["type"] == "analysis"
    assert "E-commerce" in msg["content"]


@pytest.mark.asyncio
async def test_analyze_request_sets_step_to_choices() -> None:
    analysis = _mock_domain_analysis()
    router = _make_mock_router(analysis)
    node = make_analyze_node(router)

    state = create_initial_state("Build an e-commerce platform")
    result = await node(state)

    assert result["current_step"] == STEP_CHOICES


@pytest.mark.asyncio
async def test_analyze_request_llm_failure_raises_plan_error() -> None:
    from architect.core.exceptions import PlanError

    router = MagicMock()
    router.complete_structured = AsyncMock(side_effect=RuntimeError("LLM down"))
    node = make_analyze_node(router)

    state = create_initial_state("Build something")
    with pytest.raises(PlanError):
        await node(state)
