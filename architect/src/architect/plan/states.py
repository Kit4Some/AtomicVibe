"""Plan Engine state helpers, constants, and internal models."""

from __future__ import annotations

from pydantic import BaseModel

from architect.core.models import Choice, PlanGraphState, PlanState

# ============================================================================
# Step Constants
# ============================================================================

STEP_ANALYZE = "analyze"
STEP_CHOICES = "choices"
STEP_WAITING_CHOICE = "waiting_choice"
STEP_REFINE = "refine"
STEP_FINALIZE = "finalize"
STEP_WAIT_APPROVAL = "wait_approval"

# ============================================================================
# Decision Topic Ordering
# ============================================================================

DECISION_TOPICS: list[str] = [
    "tech_stack",
    "architecture",
    "features_priority",
    "deployment",
    "authentication",
    "database",
    "testing_strategy",
    "monitoring",
]

# ============================================================================
# Internal Models
# ============================================================================


class ChoiceList(BaseModel):
    """Wrapper for structured LLM output of multiple choices."""

    choices: list[Choice]


# ============================================================================
# Helper Functions
# ============================================================================


def determine_next_topic(state: PlanState) -> str | None:
    """Return the next undecided decision topic, or None if all are decided."""
    decided = {d["topic"] for d in state["decisions"]}
    for topic in DECISION_TOPICS:
        if topic not in decided:
            return topic
    return None


def determine_next_topic_from_graph_state(state: PlanGraphState) -> str | None:
    """Return the next undecided decision topic from a PlanGraphState."""
    decided = {d["topic"] for d in state.decisions}
    for topic in DECISION_TOPICS:
        if topic not in decided:
            return topic
    return None


def create_initial_state(user_request: str) -> PlanState:
    """Create a fully initialized PlanState with zero values."""
    return PlanState(
        user_request=user_request,
        conversation_history=[],
        domain_analysis={},
        decisions=[],
        open_questions=[],
        current_step=STEP_ANALYZE,
        plan_document="",
        approved=False,
    )
