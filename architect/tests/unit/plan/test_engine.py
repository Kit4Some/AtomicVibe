"""Unit tests for PlanEngine end-to-end flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from architect.core.models import Choice, DomainAnalysis
from architect.plan.engine import PlanEngine
from architect.plan.states import (
    DECISION_TOPICS,
    STEP_WAIT_APPROVAL,
    STEP_WAITING_CHOICE,
    ChoiceList,
)


def _mock_domain_analysis() -> DomainAnalysis:
    return DomainAnalysis(
        domain="E-commerce",
        project_type="Full Stack",
        core_features=["Catalog", "Cart", "Checkout"],
        implied_requirements=["Auth"],
        complexity="medium",
        estimated_agents=3,
        initial_questions=["Payment provider?"],
    )


def _mock_choices(topic: str = "tech_stack") -> ChoiceList:
    return ChoiceList(choices=[
        Choice(
            id="A",
            label="Option A",
            description=f"First option for {topic}",
            pros=["Pro 1"],
            cons=["Con 1"],
            recommended=True,
            reason="Best fit",
        ),
        Choice(
            id="B",
            label="Option B",
            description=f"Second option for {topic}",
            pros=["Pro 2"],
            cons=["Con 2"],
            recommended=False,
            reason="Alternative",
        ),
    ])


def _make_router() -> MagicMock:
    """Create a mock LLMRouter that handles both structured and plain calls."""
    router = MagicMock()

    call_count = {"n": 0}

    async def mock_structured(messages, response_model, purpose, **kwargs):
        if response_model == DomainAnalysis:
            return _mock_domain_analysis()
        # ChoiceList
        return _mock_choices()

    async def mock_complete(messages, purpose, **kwargs):
        return "# Technical Specification\n\nThis is the plan document."

    router.complete_structured = AsyncMock(side_effect=mock_structured)
    router.complete = AsyncMock(side_effect=mock_complete)
    return router


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_returns_state_with_choices() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build an e-commerce platform")

    assert state["domain_analysis"]["domain"] == "E-commerce"
    assert state["current_step"] == STEP_WAITING_CHOICE
    assert engine.needs_user_input(state)

    choices = engine.get_current_choices(state)
    assert choices is not None
    assert len(choices) == 2
    assert choices[0].id == "A"


@pytest.mark.asyncio
async def test_respond_records_decision_and_advances() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build an API")
    state = await engine.respond(state, "A")

    # Should have recorded a decision and moved to next topic
    assert len(state["decisions"]) == 1
    assert state["decisions"][0]["topic"] == "tech_stack"
    assert state["decisions"][0]["chosen"] == "A"
    # Should present next choices
    assert state["current_step"] == STEP_WAITING_CHOICE


@pytest.mark.asyncio
async def test_full_flow_to_approval() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build an API")
    assert not engine.is_complete(state)

    # Answer all decision topics
    for _ in DECISION_TOPICS:
        assert engine.needs_user_input(state)
        state = await engine.respond(state, "A")

    # After all topics, should be at wait_approval
    assert state["current_step"] == STEP_WAIT_APPROVAL
    assert state["plan_document"] != ""

    # Approve
    state = await engine.respond(state, "approve")
    assert engine.is_complete(state)


@pytest.mark.asyncio
async def test_is_complete_false_by_default() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build something")
    assert not engine.is_complete(state)


@pytest.mark.asyncio
async def test_needs_user_input_when_waiting() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build something")
    assert engine.needs_user_input(state)
    assert state["current_step"] == STEP_WAITING_CHOICE


@pytest.mark.asyncio
async def test_get_current_choices_returns_choices() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build something")
    choices = engine.get_current_choices(state)
    assert choices is not None
    assert isinstance(choices[0], Choice)


@pytest.mark.asyncio
async def test_get_plan_document_empty_initially() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build something")
    assert engine.get_plan_document(state) == ""


@pytest.mark.asyncio
async def test_respond_approval_completes() -> None:
    router = _make_router()
    engine = PlanEngine(router)

    state = await engine.start("Build an API")
    # Fast-forward: answer all topics
    for _ in DECISION_TOPICS:
        state = await engine.respond(state, "A")

    assert state["current_step"] == STEP_WAIT_APPROVAL
    state = await engine.respond(state, "yes")
    assert engine.is_complete(state)
    assert state["approved"] is True
