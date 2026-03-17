"""Supervisor Diagnostician — error root-cause analysis."""

from __future__ import annotations

import json
import logging
from typing import Any

from architect.core.models import DiagnosisResult
from architect.llm import LLMRouter

__all__ = ["diagnose"]

log = logging.getLogger("architect.execute.supervisor.diagnostician")

_SYSTEM_PROMPT = """\
You are the Error Diagnostician inside the ARCHITECT autonomous coding system.

Your job is to analyse errors and determine the ROOT CAUSE, not just \
repeat the surface error message.

Steps:
1. CLASSIFY the error:
   - surface_error: what the error message literally says.
   - root_cause: why it actually happened (the real underlying issue).
   - error_category: one of syntax | import | type | logic | \
     interface_mismatch | dependency | environment | design_flaw.

2. PATTERN MATCH against error_history:
   - Is this the same error repeating? (set seen_before, occurrence_count)
   - Is this a variation of a previously seen pattern?
   - Did a previous fix introduce this error? (regression)

3. SEARCH knowledge_base for known solutions.

4. DETERMINE fix approach in recommendation:
   - approach: "apply_known_fix" | "retry_with_changes" | "escalate"
   - fix_description: exactly what to change.
   - confidence: 0.0-1.0 how likely the fix will work.
   - fallback: what to try if the primary fix fails.

Respond ONLY with valid JSON matching the DiagnosisResult schema.
"""


async def diagnose(
    errors: list[dict[str, Any]],
    error_history: list[dict[str, Any]],
    knowledge_base: list[dict[str, Any]],
    code_context: dict[str, str],
    *,
    llm: LLMRouter,
) -> DiagnosisResult:
    """Analyse errors and return a structured diagnosis.

    If *errors* is empty, returns a no-op cosmetic result without
    calling the LLM.
    """
    if not errors:
        return DiagnosisResult(
            surface_error="No errors reported",
            root_cause="N/A",
            error_category="syntax",
            severity="cosmetic",
            seen_before=False,
            occurrence_count=0,
            recommendation={
                "approach": "none",
                "fix_description": "No action required",
                "confidence": 1.0,
                "fallback": "",
            },
        )

    # Format code context
    code_sections: list[str] = []
    for path, content in code_context.items():
        code_sections.append(f"### `{path}`\n```python\n{content}\n```")
    code_block = "\n\n".join(code_sections) if code_sections else "(no code context)"

    user_content = (
        f"## Current Errors\n\n"
        f"```json\n{json.dumps(errors, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Error History (last 10)\n\n"
        f"```json\n{json.dumps(error_history[-10:], indent=2, ensure_ascii=False)}"
        f"\n```\n\n"
        f"## Knowledge Base (relevant entries)\n\n"
        f"```json\n{json.dumps(knowledge_base[:5], indent=2, ensure_ascii=False)}"
        f"\n```\n\n"
        f"## Code Context\n\n{code_block}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    log.info("diagnose: analysing %d error(s)", len(errors))

    result = await llm.complete_structured(
        messages=messages,
        response_model=DiagnosisResult,
        purpose="diagnose",
    )

    log.info(
        "diagnose: root_cause=%s category=%s severity=%s",
        result.root_cause[:80],
        result.error_category,
        result.severity,
    )

    return result
