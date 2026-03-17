"""Supervisor Reviewer — 6-dimension code review."""

from __future__ import annotations

import logging

from architect.core.models import ReviewResult
from architect.llm import LLMRouter

__all__ = ["review_code"]

log = logging.getLogger("architect.execute.supervisor.reviewer")

_SYSTEM_PROMPT = """\
You are a senior code reviewer inside the ARCHITECT autonomous coding system.

Review the provided code across SIX dimensions, each scored 1-5:

1. INTERFACE COMPLIANCE — Do function signatures match interfaces.md? \
   Return types correct? All required methods implemented?
2. CONVENTION ADHERENCE — Naming conventions? Import order? Error \
   handling patterns? Type hints present and correct?
3. ARCHITECTURE CONSISTENCY — Does code fit overall architecture? Module \
   boundaries respected? No circular imports?
4. IMPLEMENTATION QUALITY — Is the code functional? Edge cases handled? \
   Error handling meaningful (no bare except)? Resources managed?
5. SECURITY — No hardcoded secrets? Input validation? Injection prevention?
6. TESTABILITY — Test files included? Tests cover main functionality? \
   Tests actually assert something?

Rules:
- overall_score is the mean of the six dimension scores.
- A critical_issue is a defect that MUST be fixed before merging \
  (broken interface, security flaw, missing error handling that causes crash).
- suggestions are nice-to-haves for the next sprint.
- revision_instructions should be specific enough for the agent to fix \
  the issues without further clarification.

Respond ONLY with valid JSON matching the ReviewResult schema.
"""


async def review_code(
    code_files: dict[str, str],
    interfaces_md: str,
    conventions_md: str,
    spec_md: str,
    *,
    llm: LLMRouter,
) -> ReviewResult:
    """Run a 6-dimension code review and return the result.

    The returned :class:`ReviewResult` has its ``passed`` field
    auto-computed by a Pydantic model-validator:
    ``overall_score >= 3.5 and len(critical_issues) == 0``.
    """
    # Format code files for the prompt
    code_sections: list[str] = []
    for path, content in code_files.items():
        code_sections.append(f"### `{path}`\n```python\n{content}\n```")
    code_block = "\n\n".join(code_sections)

    user_content = (
        f"## Code to Review\n\n{code_block}\n\n"
        f"## interfaces.md\n\n{interfaces_md}\n\n"
        f"## conventions.md\n\n{conventions_md}\n\n"
        f"## spec.md (relevant sections)\n\n{spec_md}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    log.info("review_code: reviewing %d files", len(code_files))

    result = await llm.complete_structured(
        messages=messages,
        response_model=ReviewResult,
        purpose="code_review",
    )

    log.info(
        "review_code: score=%.2f passed=%s critical=%d",
        result.overall_score,
        result.passed,
        len(result.critical_issues),
    )

    return result
