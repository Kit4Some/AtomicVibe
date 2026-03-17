"""Build system prompts for coding agents."""

from __future__ import annotations

__all__ = ["build_agent_system_prompt"]


def build_agent_system_prompt(
    persona_section: str,
    conventions_md: str,
    interfaces_section: str,
) -> str:
    """Assemble the system prompt sent to a coding agent.

    Combines the agent's persona, project conventions, and relevant
    interface contracts into a single system message.
    """
    return (
        "You are a specialised coding agent for the ARCHITECT system.\n"
        "Your job is to produce production-quality code that passes review, "
        "lint, type-check, and tests on the first attempt.\n\n"
        "## Your Persona\n\n"
        f"{persona_section}\n\n"
        "## Coding Conventions\n\n"
        f"{conventions_md}\n\n"
        "## Interface Contracts\n\n"
        f"{interfaces_section}\n\n"
        "## Output Rules\n\n"
        "- Respond ONLY with valid JSON matching the AgentCodeOutput schema.\n"
        "- Include ALL source files AND their corresponding test files.\n"
        "- Each file must specify `path`, `content`, and `action` "
        '("create" | "replace" | "append").\n'
        "- If you produce exports that other agents depend on, include a "
        "SharedMemoryUpdate entry.\n"
        "- Mark completed checklist tasks in your ChecklistUpdate entries.\n"
    )
