"""Fixer — apply targeted fixes based on Diagnostician recommendations."""

from __future__ import annotations

import logging
from typing import Any

from architect.core.exceptions import FixError
from architect.core.models import AgentCodeOutput, DiagnosisResult
from architect.execute.prompts import build_fix_prompt
from architect.llm import LLMRouter

__all__ = ["apply_fix"]

log = logging.getLogger("architect.execute.fixer")

_FIX_SYSTEM_PROMPT = """\
You are a senior debugging specialist inside the ARCHITECT autonomous \
coding system.

Your job is to apply a TARGETED fix for the diagnosed error. Do NOT \
rewrite code unnecessarily — change only what is needed to resolve the \
root cause identified by the Diagnostician.

Rules:
- Include ONLY files that need to change in your output.
- Preserve existing tests; add new tests for the fix if appropriate.
- Use the same coding conventions as the rest of the project.

Respond ONLY with valid JSON matching the AgentCodeOutput schema.
"""


async def apply_fix(
    errors: list[dict[str, Any]],
    diagnosis: DiagnosisResult,
    vibe_files: dict[str, str],
    workspace_files: dict[str, str],
    *,
    llm: LLMRouter,
) -> AgentCodeOutput:
    """Generate fix code based on the Diagnostician's recommendation.

    Assembles a fix prompt with error details, diagnosis, relevant
    code, and explicit instructions, then asks the LLM to produce
    corrected files.
    """
    recommendation = diagnosis.recommendation
    fix_instructions = recommendation.get("fix_description", "")
    if not fix_instructions:
        fix_instructions = recommendation.get("approach", "Fix the error.")

    user_prompt = build_fix_prompt(
        errors=errors,
        diagnosis=diagnosis.model_dump(),
        relevant_code=workspace_files,
        fix_instructions=fix_instructions,
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _FIX_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    log.info(
        "apply_fix: category=%s severity=%s",
        diagnosis.error_category,
        diagnosis.severity,
    )

    try:
        result = await llm.complete_structured(
            messages=messages,
            response_model=AgentCodeOutput,
            purpose="fix",
        )
    except Exception as exc:
        raise FixError(
            message="Fix LLM call failed",
            detail=str(exc),
        ) from exc

    log.info("apply_fix: produced %d file fix(es)", len(result.files))

    return result
