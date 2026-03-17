"""Node: present decision choices for the next undecided topic."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from architect.core.exceptions import PlanError
from architect.core.logging import get_logger
from architect.core.models import PlanGraphState, PlanDeps
from architect.plan.prompts.choice_generator import (
    TOPIC_DESCRIPTIONS,
    build_choice_messages,
)
from architect.plan.nodes.finalize import FinalizeNode
from architect.plan.states import (
    STEP_FINALIZE,
    STEP_WAITING_CHOICE,
    ChoiceList,
    determine_next_topic_from_graph_state,
)

log = get_logger(__name__)


@dataclass
class ChoicesNode(BaseNode[PlanGraphState, PlanDeps]):
    """Generate and present choices for the next undecided topic."""

    async def run(
        self,
        ctx: GraphRunContext[PlanGraphState, PlanDeps],
    ) -> FinalizeNode | End[PlanGraphState]:
        topic = determine_next_topic_from_graph_state(ctx.state)

        if topic is None:
            log.info("present_choices.all_decided")
            ctx.state.current_step = STEP_FINALIZE
            return FinalizeNode()

        log.info("present_choices.start", topic=topic)

        try:
            messages = build_choice_messages(
                topic=topic,
                domain_analysis=ctx.state.domain_analysis,
                decisions=ctx.state.decisions,
            )
            result: ChoiceList = await ctx.deps.llm.complete_structured(
                messages=messages,
                response_model=ChoiceList,
                purpose="plan_choices",
            )
        except Exception as exc:
            raise PlanError(
                message=f"Failed to generate choices for topic '{topic}'",
                detail=str(exc),
            ) from exc

        topic_label = TOPIC_DESCRIPTIONS.get(topic, topic.replace("_", " ").title())
        choices_dicts = [c.model_dump() for c in result.choices]

        lines = [f"**{topic_label}**\n\nPlease choose one of the following:\n"]
        for c in result.choices:
            rec = " (recommended)" if c.recommended else ""
            lines.append(f"**{c.id}) {c.label}**{rec}\n{c.description}")
            lines.append(f"  Pros: {', '.join(c.pros)}")
            lines.append(f"  Cons: {', '.join(c.cons)}\n")

        content = "\n".join(lines)

        ctx.state.conversation_history.append({
            "role": "assistant",
            "content": content,
            "type": "choices",
            "topic": topic,
            "choices": choices_dicts,
        })
        ctx.state.current_step = STEP_WAITING_CHOICE

        log.info("present_choices.done", topic=topic, count=len(result.choices))

        # End turn — waiting for user input
        return End(ctx.state)
