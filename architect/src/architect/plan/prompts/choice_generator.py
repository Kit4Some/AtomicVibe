"""Prompt builder for generating decision choices."""

from __future__ import annotations

import json
from typing import Any

CHOICE_SYSTEM = """\
You are a senior software architect helping a user make technical decisions for their project.

Generate 2-4 concrete choices for the given decision topic. For each choice provide:
- id: a letter "A", "B", "C", or "D"
- label: short name (2-5 words)
- description: one-sentence explanation
- pros: 2-3 advantages
- cons: 1-2 disadvantages
- recommended: true for exactly one choice that best fits this project
- reason: why this choice is or isn't recommended for the given context

Tailor choices to the specific project domain and prior decisions. Avoid generic filler options.
Always include one "recommended" choice based on the project context.\
"""

TOPIC_DESCRIPTIONS: dict[str, str] = {
    "tech_stack": "Technology Stack (programming language, framework, database)",
    "architecture": "Architecture Pattern (monolithic, microservices, serverless, etc.)",
    "features_priority": "Core Features Priority (order by implementation priority)",
    "deployment": "Deployment Environment (cloud provider, containerization, hosting)",
    "authentication": "Authentication & Security (auth method, security strategy)",
    "database": "Database Design (schema approach, ORM, migrations)",
    "testing_strategy": "Testing Strategy (unit/integration/e2e, frameworks, coverage targets)",
    "monitoring": "Monitoring & Observability (logging, metrics, alerting)",
}


def build_choice_messages(
    topic: str,
    domain_analysis: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build messages for the choice generation LLM call."""
    topic_label = TOPIC_DESCRIPTIONS.get(topic, topic.replace("_", " ").title())

    context_parts = [
        f"Project Domain: {domain_analysis.get('domain', 'Unknown')}",
        f"Project Type: {domain_analysis.get('project_type', 'Unknown')}",
        f"Complexity: {domain_analysis.get('complexity', 'Unknown')}",
        f"Core Features: {json.dumps(domain_analysis.get('core_features', []))}",
    ]

    if decisions:
        context_parts.append("\nDecisions made so far:")
        for d in decisions:
            context_parts.append(f"  - {d['topic']}: {d['label']} ({d['rationale']})")

    context = "\n".join(context_parts)

    user_content = (
        f"Project context:\n{context}\n\n"
        f"Generate choices for: {topic_label}"
    )

    return [
        {"role": "system", "content": CHOICE_SYSTEM},
        {"role": "user", "content": user_content},
    ]
