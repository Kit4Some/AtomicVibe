"""Cross-reference validation across generated .vibe/ files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from architect.core.models import GenerateGraphState, GenerateDeps

__all__ = ["ValidateNode"]

log = logging.getLogger("architect.generate.validate")

_MAX_RETRIES = 2

# Regex patterns for extracting structured data from generated Markdown
_AGENT_ID_PATTERN = re.compile(r"Agent-[A-Z]\w*")
_PERSONA_HEADER_PATTERN = re.compile(r"^##\s+(Agent-\w+)", re.MULTILINE)
_TABLE_ROW_PATTERN = re.compile(r"^\|[^|]+\|", re.MULTILINE)


def _extract_agent_ids_from_table(content: str) -> set[str]:
    """Extract agent IDs from Markdown tables (agent.md ownership table)."""
    ids: set[str] = set()
    for match in _TABLE_ROW_PATTERN.finditer(content):
        row = match.group(0)
        for agent_match in _AGENT_ID_PATTERN.finditer(row):
            ids.add(agent_match.group(0))
    return ids


def _extract_persona_agents(content: str) -> set[str]:
    """Extract agent IDs from persona.md section headers."""
    return {m.group(1) for m in _PERSONA_HEADER_PATTERN.finditer(content)}


def _extract_task_descriptions(content: str) -> list[str]:
    """Extract task descriptions from table rows in plan.md or checklist.md."""
    tasks: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| #"):
            continue
        cols = [c.strip() for c in line.split("|")]
        # Filter header/separator rows
        cols = [c for c in cols if c and c != "#" and c != "Task"]
        if len(cols) >= 2:
            # Second column is typically the task description
            desc = cols[1].strip()
            if desc and not desc.startswith("---") and desc not in ("Task", "Status"):
                tasks.append(desc)
    return tasks


def _extract_class_and_method_names(content: str) -> set[str]:
    """Extract class and method names from interfaces.md code blocks."""
    names: set[str] = set()
    class_pattern = re.compile(r"class\s+(\w+)")
    method_pattern = re.compile(r"(?:async\s+)?def\s+(\w+)")
    in_code_block = False
    for line in content.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            for m in class_pattern.finditer(line):
                names.add(m.group(1))
            for m in method_pattern.finditer(line):
                name = m.group(1)
                if not name.startswith("_"):
                    names.add(name)
    return names


def _extract_forbidden_rules(content: str) -> list[str]:
    """Extract forbidden rules from persona.md."""
    rules: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("- [X]"):
            rule = line[5:].strip()
            if rule:
                rules.append(rule)
    return rules


def _check_plan_vs_checklist(
    plan_content: str,
    checklist_content: str,
) -> list[str]:
    """Verify all plan tasks exist in checklist."""
    errors: list[str] = []
    plan_tasks = _extract_task_descriptions(plan_content)
    checklist_tasks = _extract_task_descriptions(checklist_content)

    if not plan_tasks or not checklist_tasks:
        return errors  # Can't validate if either is empty

    checklist_text = " ".join(checklist_tasks).lower()
    missing = 0
    for task in plan_tasks:
        # Check if a reasonable substring of the task appears in checklist
        words = task.lower().split()
        key_words = [w for w in words if len(w) > 3][:3]
        if key_words and not any(w in checklist_text for w in key_words):
            missing += 1

    if missing > len(plan_tasks) * 0.3:  # More than 30% missing
        errors.append(
            f"plan↔checklist: {missing}/{len(plan_tasks)} plan tasks "
            "not found in checklist.md"
        )

    return errors


def _check_agents_consistency(
    agent_content: str,
    persona_content: str,
) -> list[str]:
    """Verify agent.md agents match persona.md sections."""
    errors: list[str] = []
    agent_ids = _extract_agent_ids_from_table(agent_content)
    persona_ids = _extract_persona_agents(persona_content)

    if not agent_ids or not persona_ids:
        return errors

    missing_in_persona = agent_ids - persona_ids
    if missing_in_persona:
        errors.append(
            f"agent↔persona: agents {missing_in_persona} "
            "in agent.md but missing from persona.md"
        )

    missing_in_agent = persona_ids - agent_ids
    if missing_in_agent:
        errors.append(
            f"agent↔persona: agents {missing_in_agent} "
            "in persona.md but missing from agent.md"
        )

    return errors


def _check_interfaces_vs_spec(
    interfaces_content: str,
    spec_content: str,
) -> list[str]:
    """Verify interface names appear in spec."""
    errors: list[str] = []
    interface_names = _extract_class_and_method_names(interfaces_content)

    if not interface_names:
        return errors

    # Check that class names from interfaces appear somewhere in spec
    spec_lower = spec_content.lower()
    missing: list[str] = []
    for name in interface_names:
        # Only check class names (PascalCase), not method names
        if name[0].isupper() and name.lower() not in spec_lower:
            missing.append(name)

    if missing:
        errors.append(
            f"interfaces↔spec: classes {missing} "
            "in interfaces.md but not referenced in spec.md"
        )

    return errors


def _check_prompts_vs_persona(
    prompts_content: str,
    persona_content: str,
) -> list[str]:
    """Verify OPERATION-GUIDE prompts reference persona constraints."""
    errors: list[str] = []
    forbidden_rules = _extract_forbidden_rules(persona_content)

    if not forbidden_rules:
        return errors

    # Check that at least some forbidden concepts appear in prompts
    prompts_lower = prompts_content.lower()
    referenced = 0
    for rule in forbidden_rules:
        # Extract key phrase from rule
        key_words = [w for w in rule.lower().split() if len(w) > 3][:2]
        if any(w in prompts_lower for w in key_words):
            referenced += 1

    if forbidden_rules and referenced < len(forbidden_rules) * 0.3:
        errors.append(
            f"prompts↔persona: only {referenced}/{len(forbidden_rules)} "
            "persona forbidden rules referenced in OPERATION-GUIDE.md"
        )

    return errors


@dataclass
class ValidateNode(BaseNode[GenerateGraphState, GenerateDeps]):
    """Cross-reference validation across all generated files.

    Returns GenerateAllNode for retry, or End with generated files.
    """

    async def run(
        self,
        ctx: GraphRunContext[GenerateGraphState, GenerateDeps],
    ) -> GenerateAllNode | End[dict[str, str]]:
        from architect.generate.nodes.gen_all import GenerateAllNode

        files = ctx.state.generated_files
        all_errors: list[str] = []

        # 1. plan.md vs checklist.md
        if "plan.md" in files and "checklist.md" in files:
            all_errors.extend(
                _check_plan_vs_checklist(files["plan.md"], files["checklist.md"])
            )

        # 2. agent.md vs persona.md
        if "agent.md" in files and "persona.md" in files:
            all_errors.extend(
                _check_agents_consistency(files["agent.md"], files["persona.md"])
            )

        # 3. interfaces.md vs spec.md
        if "interfaces.md" in files and "spec.md" in files:
            all_errors.extend(
                _check_interfaces_vs_spec(files["interfaces.md"], files["spec.md"])
            )

        # 4. OPERATION-GUIDE.md vs persona.md
        if "OPERATION-GUIDE.md" in files and "persona.md" in files:
            all_errors.extend(
                _check_prompts_vs_persona(files["OPERATION-GUIDE.md"], files["persona.md"])
            )

        ctx.state.validation_errors = all_errors

        if all_errors and ctx.state.retry_count < _MAX_RETRIES:
            ctx.state.retry_count += 1
            log.warning(
                "ValidateNode: %d errors found, retrying (retry=%d)",
                len(all_errors),
                ctx.state.retry_count,
            )
            return GenerateAllNode()

        if all_errors:
            log.warning(
                "ValidateNode: %d errors remain after max retries",
                len(all_errors),
            )
        else:
            log.info("ValidateNode: all checks passed")

        return End(ctx.state.generated_files)
