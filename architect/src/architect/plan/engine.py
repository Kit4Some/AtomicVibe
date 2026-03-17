"""Plan Engine — pydantic-graph multi-turn conversation for technical specification."""

from __future__ import annotations

from typing import Any

from pydantic_graph import Graph

from architect.core.logging import get_logger
from architect.core.models import Choice, PlanGraphState, PlanDeps
from architect.llm import LLMRouter
from architect.plan.nodes.analyze import AnalyzeNode
from architect.plan.nodes.choices import ChoicesNode
from architect.plan.nodes.finalize import FinalizeNode
from architect.plan.nodes.refine import RefineNode
from architect.plan.states import (
    STEP_WAIT_APPROVAL,
    STEP_WAITING_CHOICE,
)

log = get_logger(__name__)

# Graph must be created at module level so pydantic-graph can resolve
# forward-reference return types via the parent frame's namespace.
_PLAN_GRAPH = Graph(
    nodes=[AnalyzeNode, ChoicesNode, RefineNode, FinalizeNode],
)


class PlanEngine:
    """Multi-turn Plan Engine that guides users through technical specification creation.

    Uses a pydantic-graph Graph with short-lived runs routed by ``current_step``.
    The caller holds the ``PlanGraphState`` between turns.
    """

    def __init__(self, llm_router: LLMRouter) -> None:
        self._router = llm_router
        self._graph = _PLAN_GRAPH

    # ------------------------------------------------------------------
    # Public API (interfaces.md section 2)
    # ------------------------------------------------------------------

    async def start(self, user_request: str) -> dict[str, Any]:
        """Start a new plan session. Runs analysis + first choices presentation."""
        state = PlanGraphState(user_request=user_request)
        deps = PlanDeps(llm=self._router)

        log.info("plan_engine.start", request=user_request[:100])

        result = await self._graph.run(AnalyzeNode(), state=state, deps=deps)
        return result.output.to_typed_dict()

    async def respond(self, state_dict: dict[str, Any], user_input: str) -> dict[str, Any]:
        """Process user response and advance the plan workflow."""
        state = PlanGraphState(**state_dict)
        deps = PlanDeps(llm=self._router)

        # Append user message to history
        state.conversation_history.append({"role": "user", "content": user_input})

        current_step = state.current_step

        if current_step == STEP_WAITING_CHOICE:
            start_node: AnalyzeNode | RefineNode = RefineNode()
        elif current_step == STEP_WAIT_APPROVAL:
            if self._is_approval(user_input):
                state.approved = True
                log.info("plan_engine.approved")
                return state.to_typed_dict()
            else:
                # User wants modifications — go back to refine
                start_node = RefineNode()
        else:
            log.warning("plan_engine.unexpected_step", step=current_step)
            start_node = RefineNode()

        log.info("plan_engine.respond", step=state.current_step)

        result = await self._graph.run(start_node, state=state, deps=deps)
        return result.output.to_typed_dict()

    def is_complete(self, state: dict[str, Any]) -> bool:
        """Check if the plan has been approved."""
        return bool(state.get("approved", False))

    def needs_user_input(self, state: dict[str, Any]) -> bool:
        """Check if the engine is waiting for user input."""
        return state.get("current_step", "") in (STEP_WAITING_CHOICE, STEP_WAIT_APPROVAL)

    def get_current_choices(self, state: dict[str, Any]) -> list[Choice] | None:
        """Return the currently pending choices, or None if not in choice mode."""
        if state.get("current_step") != STEP_WAITING_CHOICE:
            return None

        for msg in reversed(state.get("conversation_history", [])):
            if msg.get("type") == "choices":
                return [Choice(**c) for c in msg.get("choices", [])]

        return None

    def get_plan_document(self, state: dict[str, Any]) -> str:
        """Return the generated plan document."""
        return state.get("plan_document", "")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_approval(user_input: str) -> bool:
        """Check if user input indicates approval."""
        normalized = user_input.strip().lower()
        approval_keywords = {"approve", "approved", "yes", "confirm", "ok", "lgtm", "승인"}
        return any(kw in normalized for kw in approval_keywords)
