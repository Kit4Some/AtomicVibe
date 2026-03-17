"""Agent HITL (Human-in-the-Loop) REST API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from architect.core.exceptions import UIError
from architect.ui.engine_manager import EngineManager
from architect.ui.schemas import (
    AgentDetail,
    AgentListResponse,
    AgentMessage,
    AgentMessageRequest,
    AgentMessageResponse,
)

router = APIRouter()

log = logging.getLogger(__name__)

# In-memory HITL message store: job_id -> agent_id -> messages
_hitl_messages: dict[str, dict[str, list[AgentMessage]]] = {}


def _get_manager(request: Request) -> EngineManager:
    return request.app.state.engine_manager  # type: ignore[no-any-return]


def _extract_agents_from_engine(manager: EngineManager, job_id: str) -> list[AgentDetail]:
    """Extract agent information from the ExecuteEngine's current state."""
    engine = manager.get_engine(job_id)
    if not engine or not engine._state:
        return []

    state = engine._state
    assignments = state.assignments
    agent_outputs = state.agent_outputs
    system_status = state.system_status

    agents: list[AgentDetail] = []
    for assignment in assignments:
        agent_id = assignment.get("agent_id", "")
        output = agent_outputs.get(agent_id, {})

        # Determine agent status
        if system_status == "paused":
            status = "waiting_for_human"
        elif output:
            files_count = len(output.get("files", []))
            status = "completed" if files_count > 0 else "running"
        else:
            status = "idle"

        # Collect HITL messages for this agent
        job_messages = _hitl_messages.get(job_id, {})
        agent_messages = job_messages.get(agent_id, [])

        agents.append(AgentDetail(
            agent_id=agent_id,
            name=assignment.get("persona_name", agent_id),
            persona=assignment.get("persona_name", ""),
            task=", ".join(str(t) for t in assignment.get("task_ids", [])),
            status=status,
            modules=assignment.get("modules", []),
            messages=agent_messages,
        ))

    return agents


@router.get("/{job_id}/agents", response_model=AgentListResponse)
async def list_agents(job_id: str, request: Request) -> AgentListResponse:
    """List all agents for a running job."""
    manager = _get_manager(request)

    if not manager.get_engine(job_id):
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    agents = _extract_agents_from_engine(manager, job_id)
    return AgentListResponse(agents=agents)


@router.get("/{job_id}/agents/{agent_id}", response_model=AgentDetail)
async def get_agent(job_id: str, agent_id: str, request: Request) -> AgentDetail:
    """Get a single agent's details including HITL messages."""
    manager = _get_manager(request)

    if not manager.get_engine(job_id):
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    agents = _extract_agents_from_engine(manager, job_id)
    for agent in agents:
        if agent.agent_id == agent_id:
            return agent

    raise UIError(message="Agent not found", detail=agent_id, status_code=404)


@router.post("/{job_id}/agents/{agent_id}/message", response_model=AgentMessageResponse)
async def send_agent_message(
    job_id: str,
    agent_id: str,
    body: AgentMessageRequest,
    request: Request,
) -> AgentMessageResponse:
    """Send a human-in-the-loop message to a specific agent and resume execution."""
    manager = _get_manager(request)
    engine = manager.get_engine(job_id)

    if not engine:
        raise UIError(message="Job not found", detail=job_id, status_code=404)

    now = datetime.now(tz=timezone.utc).isoformat()

    # Store the human message
    if job_id not in _hitl_messages:
        _hitl_messages[job_id] = {}
    if agent_id not in _hitl_messages[job_id]:
        _hitl_messages[job_id][agent_id] = []

    _hitl_messages[job_id][agent_id].append(
        AgentMessage(role="human", content=body.message, timestamp=now)
    )

    # If engine is paused (waiting for user), resume it
    if engine._state and engine._state.system_status == "paused":
        log.info("HITL: resuming engine for job=%s agent=%s", job_id, agent_id)

        # Inject user feedback into the state's error_history as guidance
        engine._state.error_history.append({
            "type": "user_guidance",
            "agent_id": agent_id,
            "message": body.message,
            "timestamp": now,
        })

        # Resume engine in background
        import asyncio
        ctx = manager._jobs.get(job_id)
        if ctx:
            ctx.status = "running"

            async def _resume() -> None:
                try:
                    await engine.resume()
                    ctx.status = "completed"
                except Exception as exc:  # noqa: BLE001
                    log.exception("Engine resume failed for job %s", job_id)
                    ctx.status = "error"
                    ctx.error = str(exc)

            ctx.task = asyncio.create_task(_resume())

        # Add agent acknowledgment
        _hitl_messages[job_id][agent_id].append(
            AgentMessage(
                role="agent",
                content=f"Received guidance. Resuming execution.",
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            )
        )

    log.info("HITL: message sent to agent=%s job=%s", agent_id, job_id)
    return AgentMessageResponse(message="Message delivered")
