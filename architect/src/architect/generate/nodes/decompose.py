"""Decompose a Plan document into independent code modules."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_graph import BaseNode, GraphRunContext

from architect.core.exceptions import GenerateError
from architect.core.models import GenerateGraphState, GenerateDeps, ModuleDefinition
from architect.generate.nodes.assign import AssignNode

__all__ = ["DecomposeNode"]

log = logging.getLogger("architect.generate.decompose")

_SYSTEM_PROMPT = """\
You are a software architect. Analyze the provided Plan document and user decisions, \
then decompose the project into independent code modules.

For each module, provide:
- name: A short snake_case identifier (e.g. "auth", "database", "api_routes")
- description: What this module does (1-2 sentences)
- directory: The relative directory path where this module lives (e.g. "src/auth/")
- dependencies: List of other module names this depends on (reference names in your list)
- estimated_files: Estimated number of source files (integer)

Rules:
- Dependencies must form a DAG (no circular dependencies)
- Each module should be cohesive — one clear responsibility
- Include test modules separately if needed
- Identify 3-10 modules depending on project complexity
"""


class ModuleList(BaseModel):
    """Wrapper for structured LLM output."""

    modules: list[ModuleDefinition] = Field(min_length=1)


@dataclass
class DecomposeNode(BaseNode[GenerateGraphState, GenerateDeps]):
    """Analyze plan_document + decisions and produce module definitions."""

    async def run(
        self,
        ctx: GraphRunContext[GenerateGraphState, GenerateDeps],
    ) -> AssignNode:
        plan_document = ctx.state.plan_document
        if not plan_document.strip():
            raise GenerateError(message="Cannot decompose: plan_document is empty")

        decisions = ctx.state.decisions
        llm = ctx.deps.llm

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "## Plan Document\n\n"
                    f"{plan_document}\n\n"
                    "## User Decisions\n\n"
                    f"{json.dumps(decisions, indent=2, ensure_ascii=False)}"
                ),
            },
        ]

        log.info("DecomposeNode: sending plan to LLM (decisions=%d)", len(decisions))

        result = await llm.complete_structured(
            messages=messages,
            response_model=ModuleList,
            purpose="generate_md",
        )

        modules = [m.model_dump() for m in result.modules]
        log.info("DecomposeNode: identified %d modules", len(modules))

        ctx.state.modules = modules
        return AssignNode()
