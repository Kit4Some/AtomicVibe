"""Node: generate the final plan document Markdown."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from architect.core.exceptions import PlanError
from architect.core.logging import get_logger
from architect.core.models import PlanGraphState, PlanDeps
from architect.plan.prompts.architect import build_plan_messages
from architect.plan.states import STEP_WAIT_APPROVAL

log = get_logger(__name__)


@dataclass
class FinalizeNode(BaseNode[PlanGraphState, PlanDeps]):
    """Generate the final plan document from all decisions."""

    async def run(
        self,
        ctx: GraphRunContext[PlanGraphState, PlanDeps],
    ) -> End[PlanGraphState]:
        domain_analysis = ctx.state.domain_analysis
        decisions = ctx.state.decisions
        features = domain_analysis.get("core_features", [])

        log.info("generate_plan.start", decisions_count=len(decisions))

        try:
            messages = build_plan_messages(domain_analysis, decisions, features)
            plan_document = await ctx.deps.llm.complete(
                messages=messages,
                purpose="plan_analysis",
                max_tokens=8192,
            )
        except Exception as exc:
            raise PlanError(
                message="Failed to generate plan document",
                detail=str(exc),
            ) from exc

        ctx.state.conversation_history.append({
            "role": "assistant",
            "content": (
                "I've generated the technical specification document. "
                "Please review it and reply with **approve** to confirm, "
                "or describe any changes you'd like."
            ),
            "type": "plan_document",
        })

        ctx.state.plan_document = plan_document
        ctx.state.current_step = STEP_WAIT_APPROVAL

        log.info("generate_plan.done", doc_length=len(plan_document))

        # End turn — waiting for user approval
        return End(ctx.state)
