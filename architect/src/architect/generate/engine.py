"""Generate Engine — transforms a Plan document into .vibe/ orchestration files."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic_graph import Graph

from architect.core.exceptions import GenerateError
from architect.core.models import GenerateGraphState, GenerateDeps
from architect.generate.nodes.assign import AssignNode
from architect.generate.nodes.decompose import DecomposeNode
from architect.generate.nodes.gen_all import GenerateAllNode
from architect.generate.nodes.validate import ValidateNode
from architect.llm import LLMRouter

__all__ = ["GenerateEngine"]

log = logging.getLogger("architect.generate.engine")

# Graph must be created at module level so pydantic-graph can resolve
# forward-reference return types via the parent frame's namespace.
_GENERATE_GRAPH = Graph(
    nodes=[DecomposeNode, AssignNode, GenerateAllNode, ValidateNode],
)


class GenerateEngine:
    """Public interface for the Generate Engine.

    Usage::

        engine = GenerateEngine(llm_router)
        files = await engine.generate(plan_document, decisions, output_path)
        # files = {"agent.md": "...", "persona.md": "...", ...}
    """

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm = llm_router
        self._graph = _GENERATE_GRAPH

    async def generate(
        self,
        plan_document: str,
        decisions: list[dict[str, Any]],
        output_path: str,
    ) -> dict[str, str]:
        """Generate all .vibe/ orchestration files.

        Args:
            plan_document: The approved Plan document (Markdown).
            decisions: List of user decision dicts from the Plan Engine.
            output_path: Directory where ``.vibe/`` folder will be created.

        Returns:
            Mapping of filename to file content for all generated files.

        Raises:
            GenerateError: If the plan_document is empty.
        """
        if not plan_document.strip():
            raise GenerateError(message="Cannot generate: plan_document is empty")

        state = GenerateGraphState(
            plan_document=plan_document,
            decisions=decisions,
            project_path=output_path,
        )
        deps = GenerateDeps(llm=self._llm)

        log.info("GenerateEngine.generate: starting (output=%s)", output_path)

        result = await self._graph.run(
            DecomposeNode(),
            state=state,
            deps=deps,
        )

        generated_files: dict[str, str] = result.output

        if state.validation_errors:
            log.warning(
                "GenerateEngine.generate: completed with %d warnings",
                len(state.validation_errors),
            )

        # Write files to disk
        if output_path and generated_files:
            vibe_dir = os.path.join(output_path, ".vibe")
            os.makedirs(vibe_dir, exist_ok=True)
            for filename, content in generated_files.items():
                filepath = os.path.join(vibe_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
            log.info(
                "GenerateEngine.generate: %d files written to %s",
                len(generated_files),
                vibe_dir,
            )

        return generated_files
