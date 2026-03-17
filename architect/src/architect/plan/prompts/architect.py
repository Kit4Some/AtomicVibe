"""Prompt builder for final plan document generation."""

from __future__ import annotations

import json
from typing import Any

ARCHITECT_SYSTEM = """\
You are a senior software architect producing a comprehensive technical specification document.

Generate a well-structured Markdown document covering all aspects of the project.
Include these sections:

## 1. Project Overview
- Domain, purpose, and scope

## 2. Technology Stack
- Language, framework, database, and key libraries with rationale

## 3. Architecture
- Pattern, component diagram (text-based), data flow

## 4. Core Features
- Prioritized feature list with brief descriptions

## 5. Module Decomposition
- Independent modules with responsibilities and dependencies

## 6. API Design
- Key endpoints or interfaces (if applicable)

## 7. Data Model
- Core entities and relationships

## 8. Authentication & Security
- Auth method, security measures

## 9. Deployment
- Environment, CI/CD approach, infrastructure

## 10. Testing Strategy
- Test types, coverage goals, key test scenarios

## 11. Monitoring & Observability
- Logging, metrics, alerting approach

## 12. Implementation Phases
- Ordered phases with tasks and dependencies

Be specific and actionable. This document will be used to automatically generate
code orchestration files.
Do NOT include actual code implementations — only specifications and designs.\
"""


def build_plan_messages(
    domain_analysis: dict[str, Any],
    decisions: list[dict[str, Any]],
    features: list[str],
) -> list[dict[str, str]]:
    """Build messages for the plan document generation LLM call."""
    user_parts = [
        "Generate a complete technical specification based on the following:",
        f"\n## Domain Analysis\n{json.dumps(domain_analysis, indent=2, ensure_ascii=False)}",
        "\n## User Decisions",
    ]

    for d in decisions:
        user_parts.append(f"- **{d['topic']}**: {d['label']} — {d['rationale']}")

    features_json = json.dumps(features, ensure_ascii=False)
    user_parts.append(f"\n## Core Features (prioritized)\n{features_json}")

    return [
        {"role": "system", "content": ARCHITECT_SYSTEM},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
