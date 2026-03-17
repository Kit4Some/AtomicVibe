"""Plan mode REST API routes — real PlanEngine integration."""

from __future__ import annotations

from fastapi import APIRouter, Request

from architect.ui.plan_session_manager import PlanSessionManager
from architect.ui.schemas import (
    AutoDecision,
    PlanApproveResponse,
    PlanChoicesResponse,
    PlanRespondRequest,
    PlanRespondResponse,
    PlanStartRequest,
    PlanStartResponse,
    PlanStatusResponse,
)

router = APIRouter()


def _get_manager(request: Request) -> PlanSessionManager:
    return request.app.state.plan_session_manager  # type: ignore[no-any-return]


@router.post("/start", status_code=201, response_model=PlanStartResponse)
async def start_plan(body: PlanStartRequest, request: Request) -> PlanStartResponse:
    """Start a new plan conversation.

    In **auto** mode, all choices are auto-selected (recommended) and the
    response includes the finished plan_document + vibe_files ready for execution.
    In **choice** mode, the first set of choices is returned for user selection.
    """
    manager = _get_manager(request)
    plan_id, first_message = await manager.start(body.user_request)

    if body.mode == "auto":
        # Auto-select all recommended choices
        auto_log = await manager.auto_run(plan_id)
        plan_document, vibe_files = await manager.approve(plan_id)
        return PlanStartResponse(
            plan_id=plan_id,
            first_message=first_message,
            mode="auto",
            auto_decisions=[AutoDecision(**d) for d in auto_log],
            plan_document=plan_document,
            vibe_files=vibe_files,
        )

    # Choice mode — return first choices for user
    choices = manager.get_choices_for_session(plan_id)
    return PlanStartResponse(plan_id=plan_id, first_message=first_message, choices=choices, mode="choice")


@router.post("/{plan_id}/respond", response_model=PlanRespondResponse)
async def respond_to_plan(
    plan_id: str, body: PlanRespondRequest, request: Request,
) -> PlanRespondResponse:
    """Send a user message or choice to the plan conversation."""
    manager = _get_manager(request)
    message, choices = await manager.respond(plan_id, body.message, body.choice_id)
    return PlanRespondResponse(message=message, choices=choices)


@router.get("/{plan_id}/status", response_model=PlanStatusResponse)
async def get_plan_status(plan_id: str, request: Request) -> PlanStatusResponse:
    """Get current plan conversation status."""
    manager = _get_manager(request)
    status = manager.get_status(plan_id)
    return PlanStatusResponse(
        step=status["step"],
        decisions_count=status["decisions_count"],
        complete=status["complete"],
    )


@router.get("/{plan_id}/choices", response_model=PlanChoicesResponse)
async def get_plan_choices(plan_id: str, request: Request) -> PlanChoicesResponse:
    """Get currently pending choices."""
    manager = _get_manager(request)
    topic, choices = manager.get_choices(plan_id)
    return PlanChoicesResponse(topic=topic, choices=choices)


@router.post("/{plan_id}/approve", response_model=PlanApproveResponse)
async def approve_plan(plan_id: str, request: Request) -> PlanApproveResponse:
    """Approve the completed plan and run Generate Engine."""
    manager = _get_manager(request)
    plan_document, vibe_files = await manager.approve(plan_id)
    return PlanApproveResponse(plan_document=plan_document, vibe_files=vibe_files)
