"""Prompt builder for the requirement analysis step."""

from __future__ import annotations

ANALYST_SYSTEM = """\
You are a senior software architect performing initial analysis of a project request.

Analyze the user's request and extract a structured domain analysis. Identify:
1. The application domain (e.g., "E-commerce", "Data Analytics", "Social Media")
2. The project type: one of "Backend API", "Frontend", "Full Stack", "CLI", "Library"
3. Core features the user explicitly or implicitly needs (3-8 items)
4. Implied requirements not stated but necessary (e.g., authentication, logging, error handling)
5. Complexity: "small" (1-2 modules), "medium" (3-5 modules), "large" (6+ modules)
6. Estimated number of coding agents needed (1-8)
7. Initial clarifying questions to ask the user (2-5 questions)

Be thorough but practical. Focus on what can be inferred from the request.\
"""


def build_analyst_messages(user_request: str) -> list[dict[str, str]]:
    """Build messages for the analyst LLM call."""
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": user_request},
    ]
