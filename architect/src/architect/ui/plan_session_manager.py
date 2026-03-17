"""Plan session registry — manages PlanEngine instances per plan_id."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from architect.config import settings
from architect.core.models import Choice, PlanState
from architect.generate import GenerateEngine
from architect.llm import LLMRouter
from architect.plan import PlanEngine

__all__ = ["PlanSessionManager"]

log = logging.getLogger(__name__)


@dataclass
class _PlanSession:
    engine: PlanEngine
    state: PlanState
    plan_id: str


class PlanSessionManager:
    """Manages plan_id → (PlanEngine, PlanState) sessions."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm = llm_router
        self._sessions: dict[str, _PlanSession] = {}

    async def start(self, user_request: str) -> tuple[str, str]:
        """Start a new plan session. Returns (plan_id, first_message)."""
        plan_id = str(uuid.uuid4())
        engine = PlanEngine(self._llm)
        state = await engine.start(user_request)

        self._sessions[plan_id] = _PlanSession(
            engine=engine, state=state, plan_id=plan_id,
        )

        # Extract first assistant message
        first_message = ""
        for msg in state.get("conversation_history", []):
            if msg.get("role") == "assistant":
                first_message = msg.get("content", "")

        log.info("PlanSessionManager.start: plan_id=%s", plan_id)
        return plan_id, first_message

    async def respond(
        self, plan_id: str, message: str, choice_id: str | None = None,
    ) -> tuple[str, list[Choice] | None]:
        """Send user response, return (assistant_message, choices_or_none)."""
        session = self._get_session(plan_id)
        engine = session.engine

        user_input = choice_id if choice_id else message
        session.state = await engine.respond(session.state, user_input)

        # Extract latest assistant message
        assistant_message = ""
        history = session.state.get("conversation_history", [])
        if history and history[-1].get("role") == "assistant":
            assistant_message = history[-1].get("content", "")

        choices = engine.get_current_choices(session.state)
        return assistant_message, choices

    def get_choices_for_session(self, plan_id: str) -> list[Choice] | None:
        """Return current choices for a session, or None."""
        session = self._sessions.get(plan_id)
        if not session:
            return None
        return session.engine.get_current_choices(session.state)

    def get_status(self, plan_id: str) -> dict[str, Any]:
        """Return step, decisions_count, complete."""
        session = self._get_session(plan_id)
        state = session.state
        engine = session.engine
        return {
            "step": state.get("current_step", ""),
            "decisions_count": len(state.get("decisions", [])),
            "complete": engine.is_complete(state),
        }

    def get_choices(self, plan_id: str) -> tuple[str, list[Choice]]:
        """Return (topic, choices) for the current pending decision."""
        session = self._get_session(plan_id)
        choices = session.engine.get_current_choices(session.state) or []

        # Extract topic from conversation history
        topic = ""
        for msg in reversed(session.state.get("conversation_history", [])):
            if msg.get("type") == "choices":
                topic = msg.get("topic", "")
                break

        return topic, choices

    async def auto_run(self, plan_id: str) -> list[dict[str, Any]]:
        """Auto-select recommended choices until plan is complete.

        Returns a log of each auto-selected decision: [{topic, choice_id, label}, ...].
        """
        session = self._get_session(plan_id)
        engine = session.engine
        auto_log: list[dict[str, Any]] = []
        max_rounds = 20  # safety limit

        for _ in range(max_rounds):
            choices = engine.get_current_choices(session.state)
            if not choices:
                # No choices pending — check if complete or waiting for approval
                if engine.is_complete(session.state):
                    break
                # Try to approve
                session.state = await engine.respond(session.state, "approve")
                if engine.is_complete(session.state):
                    break
                continue

            # Pick recommended choice, or first if none recommended
            recommended = next((c for c in choices if c.recommended), choices[0])
            auto_log.append({
                "choice_id": recommended.id,
                "label": recommended.label,
            })

            log.info(
                "auto_run: plan=%s auto-selected [%s] %s",
                plan_id, recommended.id, recommended.label,
            )

            session.state = await engine.respond(session.state, recommended.id)

            if engine.is_complete(session.state):
                break

        return auto_log

    async def approve(self, plan_id: str) -> tuple[str, dict[str, str]]:
        """Approve the plan, run Generate Engine. Returns (plan_document, vibe_files)."""
        session = self._get_session(plan_id)
        engine = session.engine

        if not engine.is_complete(session.state):
            session.state = await engine.respond(session.state, "approve")

        plan_document = engine.get_plan_document(session.state)
        decisions = session.state.get("decisions", [])

        # Run Generate Engine to produce .vibe/ orchestration files
        gen_engine = GenerateEngine(self._llm)
        output_path = str(settings.workspace_path)
        vibe_files = await gen_engine.generate(plan_document, decisions, output_path)

        log.info(
            "PlanSessionManager.approve: plan_id=%s generated %d vibe files",
            plan_id, len(vibe_files),
        )

        return plan_document, vibe_files

    def _get_session(self, plan_id: str) -> _PlanSession:
        session = self._sessions.get(plan_id)
        if not session:
            from architect.core.exceptions import UIError
            raise UIError(
                message="Plan session not found",
                detail=plan_id,
                status_code=404,
            )
        return session
