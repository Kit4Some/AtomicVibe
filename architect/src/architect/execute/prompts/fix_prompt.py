"""Build prompts for the fix agent."""

from __future__ import annotations

import json
from typing import Any

__all__ = ["build_fix_prompt"]


def build_fix_prompt(
    errors: list[dict[str, Any]],
    diagnosis: dict[str, Any],
    relevant_code: dict[str, str],
    fix_instructions: str,
) -> str:
    """Assemble the user prompt for an error-fix LLM call.

    Provides the LLM with error details, root-cause diagnosis, the
    failing code, and explicit fix instructions.
    """
    parts: list[str] = []

    # -- Error details --
    parts.append("## Errors to Fix\n")
    parts.append(f"```json\n{json.dumps(errors, indent=2)}\n```\n")

    # -- Diagnosis --
    parts.append("## Diagnosis\n")
    root_cause = diagnosis.get("root_cause", "unknown")
    category = diagnosis.get("error_category", "unknown")
    severity = diagnosis.get("severity", "unknown")
    parts.append(f"- **Root cause**: {root_cause}")
    parts.append(f"- **Category**: {category}")
    parts.append(f"- **Severity**: {severity}")
    recommendation = diagnosis.get("recommendation", {})
    if recommendation:
        parts.append(
            f"- **Recommended approach**: "
            f"{recommendation.get('fix_description', recommendation.get('approach', ''))}"
        )
    parts.append("")

    # -- Relevant code --
    if relevant_code:
        parts.append("## Relevant Code\n")
        for path, content in relevant_code.items():
            parts.append(f"### `{path}`\n```python\n{content}\n```\n")

    # -- Fix instructions --
    if fix_instructions:
        parts.append("## Fix Instructions\n")
        parts.append(fix_instructions)
        parts.append("")

    parts.append(
        "Respond with valid JSON matching AgentCodeOutput. "
        "Include ONLY the files that need to change."
    )

    return "\n".join(parts)
