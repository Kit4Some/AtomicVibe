"""Node: analyze the user's initial request to produce a DomainAnalysis."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from architect.core.exceptions import PlanError
from architect.core.logging import get_logger
from architect.core.models import DomainAnalysis, PlanGraphState, PlanDeps
from architect.plan.prompts.analyst import build_analyst_messages
from architect.plan.nodes.choices import ChoicesNode
from architect.plan.states import STEP_CHOICES

log = get_logger(__name__)


@dataclass
class AnalyzeNode(BaseNode[PlanGraphState, PlanDeps]):
    """Analyze the user request and extract a structured DomainAnalysis."""

    async def run(
        self,
        ctx: GraphRunContext[PlanGraphState, PlanDeps],
    ) -> ChoicesNode:
        user_request = ctx.state.user_request
        log.info("analyze_request.start", user_request=user_request[:100])

        try:
            messages = build_analyst_messages(user_request)
            analysis: DomainAnalysis = await ctx.deps.llm.complete_structured(
                messages=messages,
                response_model=DomainAnalysis,
                purpose="plan_analysis",
            )
        except Exception as exc:
            raise PlanError(
                message="Failed to analyze user request",
                detail=str(exc),
            ) from exc

        analysis_dict = analysis.model_dump()

        ctx.state.conversation_history.append({
            "role": "assistant",
            "content": (
                f"I've analyzed your request. This looks like a **{analysis.project_type}** "
                f"project in the **{analysis.domain}** domain with "
                f"**{analysis.complexity}** complexity.\n\n"
                f"Core features identified: {', '.join(analysis.core_features)}"
            ),
            "type": "analysis",
        })

        ctx.state.domain_analysis = analysis_dict
        ctx.state.open_questions = list(analysis.initial_questions)
        ctx.state.current_step = STEP_CHOICES

        log.info(
            "analyze_request.done",
            domain=analysis.domain,
            complexity=analysis.complexity,
        )

        return ChoicesNode()
