"""Supervisor Strategist — high-level strategic decision making."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from architect.core.models import DiagnosisResult
from architect.llm import LLMRouter

__all__ = ["strategize"]

log = logging.getLogger("architect.execute.supervisor.strategist")

_SYSTEM_PROMPT = """\
You are the Strategist inside the ARCHITECT autonomous coding system.

When errors persist or escalation is needed, you choose ONE of seven \
strategies:

1. RETRY_WITH_GUIDANCE — First/second failure, clear fix available. \
   Send specific instructions. Risk: Low.
2. CHANGE_IMPLEMENTATION — Same approach failed 2+ times or design \
   flaw detected. Change library/pattern/algorithm. Risk: Medium.
3. SPLIT_TASK — Task too complex for a single pass. Decompose into \
   smaller sub-tasks. Risk: Low.
4. REASSIGN_AGENT — Agent consistently fails at this task type. \
   Assign to a different agent with context. Risk: Low-Medium.
5. MODIFY_INTERFACE — Interface mismatch is root cause. Update \
   interfaces.md and notify dependents. Risk: High (cascading).
6. ROLLBACK_AND_RETRY — A fix introduced regressions. Revert to \
   last known good state. Risk: Medium.
7. REQUEST_USER_INPUT — Budget/iteration limit near, or fundamental \
   ambiguity. Pause and ask user. Risk: None.

Consider:
- Budget remaining and iteration count.
- Previous decisions and their outcomes.
- Risk vs. reward of each strategy.

Respond ONLY with valid JSON matching the StrategyDecision schema.
"""

_VALID_STRATEGIES = frozenset({
    "RETRY_WITH_GUIDANCE",
    "CHANGE_IMPLEMENTATION",
    "SPLIT_TASK",
    "REASSIGN_AGENT",
    "MODIFY_INTERFACE",
    "ROLLBACK_AND_RETRY",
    "REQUEST_USER_INPUT",
})


# ------------------------------------------------------------------
# Wrapper Pydantic models
# ------------------------------------------------------------------


class _StrategyAction(BaseModel):
    type: str
    target: str = ""
    change: str = ""
    details: str = ""
    affected_agents: list[str] = Field(default_factory=list)


class StrategyDecision(BaseModel):
    """Structured output from the Strategist LLM call."""

    decision: str
    rationale: str
    actions: list[_StrategyAction] = Field(default_factory=list)
    risk_assessment: str = ""
    estimated_additional_cost: str = ""
    estimated_additional_iterations: int = 1


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def strategize(
    diagnosis: DiagnosisResult,
    spec_md: str,
    decisions: list[dict[str, Any]],
    budget_remaining: float,
    iterations_remaining: int,
    *,
    llm: LLMRouter,
) -> dict[str, Any]:
    """Choose a strategic response to a diagnosed error.

    If budget or iterations are exhausted, returns
    ``REQUEST_USER_INPUT`` without an LLM call.
    """
    # Guardrail: exhausted resources → ask user
    if budget_remaining <= 0 or iterations_remaining <= 0:
        log.warning(
            "strategize: resources exhausted (budget=%.2f, iter=%d) "
            "→ REQUEST_USER_INPUT",
            budget_remaining,
            iterations_remaining,
        )
        return StrategyDecision(
            decision="REQUEST_USER_INPUT",
            rationale=(
                f"Budget remaining: ${budget_remaining:.2f}, "
                f"iterations remaining: {iterations_remaining}. "
                "Cannot proceed without user approval."
            ),
            actions=[],
            risk_assessment="None — pausing execution.",
            estimated_additional_iterations=0,
        ).model_dump()

    user_content = (
        f"## Diagnosis\n\n"
        f"- Surface error: {diagnosis.surface_error}\n"
        f"- Root cause: {diagnosis.root_cause}\n"
        f"- Category: {diagnosis.error_category}\n"
        f"- Severity: {diagnosis.severity}\n"
        f"- Seen before: {diagnosis.seen_before} "
        f"(count: {diagnosis.occurrence_count})\n"
        f"- Recommendation: "
        f"{json.dumps(diagnosis.recommendation, ensure_ascii=False)}\n\n"
        f"## Budget & Iterations\n\n"
        f"- Budget remaining: ${budget_remaining:.2f}\n"
        f"- Iterations remaining: {iterations_remaining}\n\n"
        f"## Previous Strategic Decisions\n\n"
        f"{json.dumps(decisions[-10:], indent=2, ensure_ascii=False)}\n\n"
        f"## spec.md (relevant sections)\n\n{spec_md}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    log.info("strategize: evaluating strategies for %s", diagnosis.error_category)

    result = await llm.complete_structured(
        messages=messages,
        response_model=StrategyDecision,
        purpose="strategize",
    )

    log.info("strategize: chose %s — %s", result.decision, result.rationale[:80])

    return result.model_dump()
