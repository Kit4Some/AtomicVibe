"""Unit tests for the choices node and topic helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from architect.core.models import Choice
from architect.plan.nodes.choices import make_choices_node
from architect.plan.states import (
    DECISION_TOPICS,
    STEP_FINALIZE,
    STEP_WAITING_CHOICE,
    ChoiceList,
    create_initial_state,
    determine_next_topic,
)


def _sample_choices() -> ChoiceList:
    return ChoiceList(choices=[
        Choice(
            id="A",
            label="Python + FastAPI",
            description="Modern async Python API framework",
            pros=["Fast", "Great docs"],
            cons=["Smaller ecosystem"],
            recommended=True,
            reason="Best fit for this project",
        ),
        Choice(
            id="B",
            label="Node.js + Express",
            description="Popular JavaScript backend",
            pros=["Huge ecosystem", "Same language as frontend"],
            cons=["Callback complexity"],
            recommended=False,
            reason="Good but not optimal here",
        ),
    ])


def _make_mock_router(choice_list: ChoiceList) -> MagicMock:
    router = MagicMock()
    router.complete_structured = AsyncMock(return_value=choice_list)
    return router


# ---------------------------------------------------------------------------
# determine_next_topic tests
# ---------------------------------------------------------------------------


def test_determine_next_topic_returns_first_when_no_decisions() -> None:
    state = create_initial_state("test")
    result = determine_next_topic(state)
    assert result == DECISION_TOPICS[0]


def test_determine_next_topic_skips_decided() -> None:
    state = create_initial_state("test")
    state["decisions"] = [{"topic": "tech_stack", "chosen": "A", "label": "X", "rationale": "Y"}]
    result = determine_next_topic(state)
    assert result == "architecture"


def test_determine_next_topic_returns_none_when_all_decided() -> None:
    state = create_initial_state("test")
    state["decisions"] = [
        {"topic": t, "chosen": "A", "label": "X", "rationale": "Y"}
        for t in DECISION_TOPICS
    ]
    result = determine_next_topic(state)
    assert result is None


# ---------------------------------------------------------------------------
# present_choices node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_present_choices_generates_for_first_topic() -> None:
    router = _make_mock_router(_sample_choices())
    node = make_choices_node(router)

    state = create_initial_state("Build an API")
    state["domain_analysis"] = {"domain": "Web", "project_type": "Backend API", "core_features": []}
    state["current_step"] = "choices"

    result = await node(state)

    assert result["current_step"] == STEP_WAITING_CHOICE
    assert len(result["conversation_history"]) == 1
    msg = result["conversation_history"][0]
    assert msg["type"] == "choices"
    assert msg["topic"] == "tech_stack"
    assert len(msg["choices"]) == 2


@pytest.mark.asyncio
async def test_present_choices_skips_decided_topics() -> None:
    router = _make_mock_router(_sample_choices())
    node = make_choices_node(router)

    state = create_initial_state("Build an API")
    state["domain_analysis"] = {"domain": "Web", "project_type": "Backend API", "core_features": []}
    state["decisions"] = [{"topic": "tech_stack", "chosen": "A", "label": "X", "rationale": "Y"}]
    state["current_step"] = "choices"

    result = await node(state)

    msg = result["conversation_history"][0]
    assert msg["topic"] == "architecture"


@pytest.mark.asyncio
async def test_present_choices_all_decided_sets_finalize() -> None:
    router = MagicMock()
    node = make_choices_node(router)

    state = create_initial_state("Build an API")
    state["decisions"] = [
        {"topic": t, "chosen": "A", "label": "X", "rationale": "Y"}
        for t in DECISION_TOPICS
    ]
    state["current_step"] = "choices"

    result = await node(state)

    assert result["current_step"] == STEP_FINALIZE
    router.complete_structured.assert_not_called()
