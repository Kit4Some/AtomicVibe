"""Node: process user's choice and record a decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_graph import BaseNode, GraphRunContext

from architect.core.logging import get_logger
from architect.core.models import Decision, PlanGraphState, PlanDeps
from architect.plan.nodes.choices import ChoicesNode
from architect.plan.states import STEP_CHOICES

log = get_logger(__name__)


def _find_last_choices_message(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the most recent choices message in conversation history."""
    for msg in reversed(history):
        if msg.get("type") == "choices":
            return msg
    return None


def _match_choice(
    user_input: str, choices: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match user input to a choice by ID or label (case-insensitive)."""
    normalized = user_input.strip().upper()

    # Match by ID (e.g., "A", "B")
    for c in choices:
        if c["id"].upper() == normalized:
            return c

    # Match by label (case-insensitive substring)
    lower_input = user_input.strip().lower()
    for c in choices:
        if c["label"].lower() == lower_input:
            return c

    return None


@dataclass
class RefineNode(BaseNode[PlanGraphState, PlanDeps]):
    """Extract user's selection and record it as a Decision, then advance to choices."""

    async def run(
        self,
        ctx: GraphRunContext[PlanGraphState, PlanDeps],
    ) -> ChoicesNode:
        history = ctx.state.conversation_history

        # Find last user message
        user_input = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        # Find the choices that were presented
        choices_msg = _find_last_choices_message(history)
        topic = choices_msg["topic"] if choices_msg else "unknown"
        choices = choices_msg.get("choices", []) if choices_msg else []

        log.info("refine_spec.start", topic=topic, user_input=user_input[:50])

        matched = _match_choice(user_input, choices)

        if matched:
            decision = Decision(
                topic=topic,
                chosen=matched["id"],
                label=matched["label"],
                rationale=matched.get("reason", user_input),
            )
        else:
            # Free-text: treat as custom specification
            decision = Decision(
                topic=topic,
                chosen="custom",
                label=user_input[:50],
                rationale=user_input,
            )

        ctx.state.decisions.append(decision.model_dump())

        # Remove from open_questions if present
        ctx.state.open_questions = [
            q for q in ctx.state.open_questions
            if topic.replace("_", " ") not in q.lower()
        ]

        ctx.state.current_step = STEP_CHOICES

        log.info("refine_spec.done", topic=topic, chosen=decision.chosen)

        return ChoicesNode()
