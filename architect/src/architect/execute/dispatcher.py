"""Dispatcher — assemble prompts and call the LLM as a coding agent."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from architect.core.exceptions import DispatchError
from architect.core.models import AgentCodeOutput
from architect.execute.prompts import (
    build_agent_system_prompt,
    build_agent_user_prompt,
)
from architect.llm import LLMRouter

__all__ = ["dispatch", "dispatch_parallel"]

log = logging.getLogger("architect.execute.dispatcher")

_FIX_SYSTEM = (
    "You are a specialised coding agent for the ARCHITECT system.\n"
    "Produce production-quality code. Respond ONLY with valid JSON "
    "matching the AgentCodeOutput schema."
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_persona_section(persona_md: str, agent_id: str) -> str:
    """Extract the persona section for *agent_id* from persona.md.

    Sections are delimited by ``## Agent-X:`` headings or ``---``
    horizontal rules.
    """
    pattern = rf"(##\s*{re.escape(agent_id)}\s*:.*?)(?=\n##\s*Agent-|\n---|\Z)"
    match = re.search(pattern, persona_md, re.DOTALL)
    if match:
        return match.group(1).strip()
    return f"(No persona found for {agent_id})"


def _extract_interfaces_section(interfaces_md: str, agent_id: str) -> str:
    """Best-effort extraction of the interface section relevant to *agent_id*."""
    # Try to find a section header mentioning the agent
    pattern = rf"(##.*?{re.escape(agent_id)}.*?)(?=\n##|\Z)"
    match = re.search(pattern, interfaces_md, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: return the full interfaces doc (will be truncated by LLM context)
    return interfaces_md


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def dispatch(
    agent_id: str,
    task_ids: list[int],
    vibe_files: dict[str, str],
    workspace_files: dict[str, str],
    injected_knowledge: list[str],
    errors: list[dict[str, Any]] | None,
    *,
    llm: LLMRouter,
) -> AgentCodeOutput:
    """Dispatch a single coding-agent LLM call.

    Assembles the system prompt (persona + conventions + interfaces)
    and user prompt (tasks + spec + shared-memory + knowledge + code
    + prior errors), then calls the LLM with
    ``purpose="code_generation"``.
    """
    persona_md = vibe_files.get("persona.md", "")
    conventions_md = vibe_files.get("conventions.md", "")
    interfaces_md = vibe_files.get("interfaces.md", "")
    spec_md = vibe_files.get("spec.md", "")
    shared_memory_md = vibe_files.get("shared-memory.md", "")

    persona_section = _extract_persona_section(persona_md, agent_id)
    interfaces_section = _extract_interfaces_section(interfaces_md, agent_id)

    system_prompt = build_agent_system_prompt(
        persona_section=persona_section,
        conventions_md=conventions_md,
        interfaces_section=interfaces_section,
    )

    # Build tasks list from vibe task IDs
    tasks = [{"task_id": tid, "description": f"Task #{tid}"} for tid in task_ids]

    user_prompt = build_agent_user_prompt(
        tasks=tasks,
        spec_section=spec_md,
        shared_memory_exports=shared_memory_md,
        injected_knowledge=injected_knowledge,
        existing_code=workspace_files,
        previous_errors=errors,
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    log.info(
        "dispatch: agent=%s tasks=%s knowledge=%d",
        agent_id,
        task_ids,
        len(injected_knowledge),
    )

    try:
        result = await llm.complete_structured(
            messages=messages,
            response_model=AgentCodeOutput,
            purpose="code_generation",
        )
    except Exception as exc:
        raise DispatchError(
            message=f"Dispatch failed for {agent_id}",
            detail=str(exc),
        ) from exc

    log.info(
        "dispatch: agent=%s produced %d files, %d tests",
        agent_id,
        len(result.files),
        len(result.tests),
    )

    return result


async def dispatch_parallel(
    assignments: list[dict[str, Any]],
    vibe_files: dict[str, str],
    workspace_files: dict[str, str],
    *,
    llm: LLMRouter,
    max_agents: int | None = None,
) -> dict[str, AgentCodeOutput]:
    """Dispatch multiple agents in parallel using ``asyncio.gather``.

    Returns a dict mapping ``agent_id`` → ``AgentCodeOutput``.
    Concurrency is limited by the current tier's max agent count
    (or *max_agents* if provided).  Agents that fail are wrapped in
    :class:`DispatchError` and collected; the rest succeed normally.
    """
    from architect.llm.models import get_max_agents

    limit = max_agents or get_max_agents()
    sem = asyncio.Semaphore(limit)

    log.info("dispatch_parallel: %d assignments, concurrency limit=%d", len(assignments), limit)

    async def _single(assignment: dict[str, Any]) -> tuple[str, AgentCodeOutput]:
        agent_id = assignment["agent_id"]
        async with sem:
            return (
                agent_id,
                await dispatch(
                    agent_id=agent_id,
                    task_ids=assignment.get("task_ids", []),
                    vibe_files=vibe_files,
                    workspace_files=workspace_files,
                    injected_knowledge=assignment.get("injected_knowledge", []),
                    errors=None,
                    llm=llm,
                ),
            )

    results = await asyncio.gather(
        *[_single(a) for a in assignments],
        return_exceptions=True,
    )

    outputs: dict[str, AgentCodeOutput] = {}
    for i, res in enumerate(results):
        agent_id = assignments[i]["agent_id"]
        if isinstance(res, BaseException):
            log.error("dispatch_parallel: %s failed: %s", agent_id, res)
            if not isinstance(res, DispatchError):
                res = DispatchError(
                    message=f"Dispatch failed for {agent_id}",
                    detail=str(res),
                )
            raise res
        outputs[res[0]] = res[1]

    return outputs
