"""Hub node that generates all 11 .vibe/ MD files in parallel."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any

import jinja2
from pydantic_graph import BaseNode, GraphRunContext

from architect.core.models import GenerateGraphState, GenerateDeps

__all__ = ["GenerateAllNode"]

log = logging.getLogger("architect.generate.gen_all")

# Concurrency limit to avoid rate-limit storms
_MAX_CONCURRENT = 5

# All 11 output filenames
GENERATED_FILES = [
    "agent.md",
    "persona.md",
    "plan.md",
    "spec.md",
    "checklist.md",
    "interfaces.md",
    "conventions.md",
    "shared-memory.md",
    "knowledge.md",
    "errors.md",
    "OPERATION-GUIDE.md",
]


def _create_jinja_env() -> jinja2.Environment:
    """Create a Jinja2 environment that loads from the templates package."""
    templates_path = resources.files("architect.generate") / "templates"
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_path)),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _today() -> str:
    return date.today().isoformat()


def _strip_code_fences(text: str) -> str:
    """Remove Markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


# ============================================================================
# Helper: build common context from state
# ============================================================================


def _agents_from_state(state: GenerateGraphState) -> list[dict[str, Any]]:
    """Extract agent list from assignments."""
    return state.agent_assignments


def _modules_from_state(state: GenerateGraphState) -> list[dict[str, Any]]:
    return state.modules


def _decisions_from_state(state: GenerateGraphState) -> list[dict[str, Any]]:
    return state.decisions


def _project_name(state: GenerateGraphState) -> str:
    """Infer project name from plan_document first line or fallback."""
    plan = state.plan_document
    for line in plan.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "Project"


# ============================================================================
# 11 individual generators
# ============================================================================


async def _gen_agent_md(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    agents = _agents_from_state(state)
    modules = _modules_from_state(state)
    decisions = _decisions_from_state(state)

    async with sem:
        overview_and_tree = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate two sections for a project orchestration document:\n"
                        "1. A concise system overview paragraph (2-4 sentences)\n"
                        "2. A directory tree showing all modules\n\n"
                        "Format:\n"
                        "OVERVIEW:\n<overview text>\n\n"
                        "TREE:\n<tree text>"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
                        f"Decisions: {json.dumps(decisions, ensure_ascii=False)}"
                    ),
                },
            ],
            purpose="generate_md",
        )

    overview = ""
    tree = ""
    if "OVERVIEW:" in overview_and_tree and "TREE:" in overview_and_tree:
        parts = overview_and_tree.split("TREE:")
        overview = parts[0].replace("OVERVIEW:", "").strip()
        tree = parts[1].strip()
    else:
        overview = overview_and_tree.strip()
        tree = "\n".join(f"{m.get('directory', '')}/" for m in modules)

    agent_ids = sorted({a.get("agent_id", "") for a in agents})
    matrix_header = "          " + "  ".join(f"{aid:>5}" for aid in agent_ids)
    matrix_rows = [matrix_header]
    for aid in agent_ids:
        row = f"{aid:>9} "
        agent = next((a for a in agents if a.get("agent_id") == aid), None)
        parallels = agent.get("can_parallel_with", []) if agent else []
        for other in agent_ids:
            if other == aid:
                row += "   - "
            elif other in parallels:
                row += " [OK]"
            else:
                row += "[DEP]"
        matrix_rows.append(row)
    parallel_matrix = "\n".join(matrix_rows)

    phase_map: dict[int, list[str]] = {}
    for a in agents:
        p = a.get("phase", 1)
        phase_map.setdefault(p, []).append(a.get("agent_id", ""))
    phases = []
    for num in sorted(phase_map):
        ids = " + ".join(phase_map[num])
        mode = "병렬" if len(phase_map[num]) > 1 else "집중"
        phases.append({
            "number": num, "mode": mode, "description": ids,
        })

    rules = [
        "자기 디렉토리만 생성/수정. 위반 시 Reviewer가 차단.",
        "공유 모듈은 담당 Agent만 관리, 전원 import 가능.",
        "interfaces.md 변경 시 shared-memory.md ALERT 필수.",
        "완료 시: checklist + shared-memory + knowledge 반드시 업데이트.",
        "다른 Agent 코드 수정 필요 시 shared-memory.md에 REQUEST.",
    ]

    template = env.get_template("agent.md.j2")
    content = template.render(
        project_name=_project_name(state),
        date=_today(),
        system_overview=overview,
        directory_tree=tree,
        agents=agents,
        rules=rules,
        parallel_matrix=parallel_matrix,
        phases=phases,
    )
    return ("agent.md", content)


async def _gen_persona(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    agents = _agents_from_state(state)
    modules = _modules_from_state(state)
    decisions = _decisions_from_state(state)

    async with sem:
        persona_json = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "For each agent, generate persona details in JSON array format.\n"
                        "Each object must have:\n"
                        '- "agent_id": string\n'
                        '- "persona_name": string\n'
                        '- "instructions": string (role description, key principles, 3-5 lines)\n'
                        '- "forbidden": list of strings (things this agent must NOT do)\n'
                        '- "scope": string (directories this agent manages)\n'
                        '- "knowledge": list of strings (relevant docs/references)\n'
                        '- "tools": list of strings (tools/commands the agent uses)\n'
                        "Respond with ONLY the JSON array."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Agents: {json.dumps(agents, ensure_ascii=False)}\n"
                        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
                        f"Decisions: {json.dumps(decisions, ensure_ascii=False)}"
                    ),
                },
            ],
            purpose="generate_md",
        )

    try:
        cleaned = _strip_code_fences(persona_json)
        agent_details = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        agent_details = [
            {
                "agent_id": a.get("agent_id", ""),
                "persona_name": a.get("persona_name", ""),
                "instructions": f"역할: {a.get('persona_name', '')}. 담당 모듈 구현.",
                "forbidden": [f"{d} 외 파일 수정 금지" for d in a.get("modules", [])],
                "scope": ", ".join(a.get("modules", [])),
                "knowledge": [],
                "tools": ["Python 3.12+", "pytest"],
            }
            for a in agents
        ]

    template = env.get_template("persona.md.j2")
    content = template.render(agents=agent_details)
    return ("persona.md", content)


async def _gen_plan_md(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    modules = _modules_from_state(state)
    agents = _agents_from_state(state)
    decisions = _decisions_from_state(state)

    async with sem:
        plan_json = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a phased implementation plan as JSON.\n"
                        "Format: [{\"number\": int, \"title\": str, \"agent_labels\": str, "
                        "\"description\": str, \"tasks\": [{\"number\": int, \"description\": str, "
                        "\"agent\": str, \"dependencies\": str, \"priority\": str}]}]\n"
                        "Tasks should be numbered sequentially across phases (1, 2, 3...).\n"
                        "Priority: HIGH | MEDIUM | LOW.\n"
                        "Respond with ONLY the JSON array."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
                        f"Agents: {json.dumps(agents, ensure_ascii=False)}\n"
                        f"Decisions: {json.dumps(decisions, ensure_ascii=False)}"
                    ),
                },
            ],
            purpose="generate_md",
        )

    try:
        cleaned = _strip_code_fences(plan_json)
        phases = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        phases = []

    template = env.get_template("plan.md.j2")
    content = template.render(
        project_name=_project_name(state),
        phases=phases,
    )
    return ("plan.md", content)


async def _gen_spec(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    modules = _modules_from_state(state)
    agents = _agents_from_state(state)
    decisions = _decisions_from_state(state)
    plan_doc = state.plan_document

    section_prompts = [
        ("Core Models",
         "Generate Pydantic model definitions for all data structures."),
        ("State Definitions",
         "Generate TypedDict state definitions for each engine/pipeline."),
        ("Architecture & Engine Design",
         "Generate detailed architecture and engine designs for each module."),
        ("Validation & Safety",
         "Generate validation pipeline steps, safety limits, and config."),
    ]

    context = (
        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
        f"Agents: {json.dumps(agents, ensure_ascii=False)}\n"
        f"Decisions: {json.dumps(decisions, ensure_ascii=False)}\n"
        f"Plan: {plan_doc[:3000]}"
    )

    sections = []
    for i, (title, instruction) in enumerate(section_prompts, 1):
        async with sem:
            section_content = await llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are writing section {i} of a technical specification.\n"
                            f"Section title: {title}\n"
                            f"Task: {instruction}\n"
                            "Include code blocks where appropriate.\n"
                            "Write in a clear, technical style."
                        ),
                    },
                    {"role": "user", "content": context},
                ],
                purpose="generate_md",
                max_tokens=8192,
            )
        sections.append({"number": i, "title": title, "content": section_content.strip()})

    template = env.get_template("spec.md.j2")
    content = template.render(
        project_name=_project_name(state),
        sections=sections,
    )
    return ("spec.md", content)


async def _gen_checklist(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    modules = _modules_from_state(state)
    agents = _agents_from_state(state)

    async with sem:
        checklist_json = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a task checklist as JSON for progress tracking.\n"
                        "Format: [{\"number\": int, \"title\": str, "
                        "\"tasks\": [{\"number\": int, \"description\": str, "
                        "\"agent\": str, \"notes\": str}]}]\n"
                        "Group tasks by implementation phase.\n"
                        "Task numbers should be sequential across all phases.\n"
                        "Respond with ONLY the JSON array."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
                        f"Agents: {json.dumps(agents, ensure_ascii=False)}"
                    ),
                },
            ],
            purpose="generate_md",
        )

    try:
        cleaned = _strip_code_fences(checklist_json)
        phases = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        phases = []

    total_tasks = sum(len(p.get("tasks", [])) for p in phases)

    template = env.get_template("checklist.md.j2")
    content = template.render(
        date=_today(),
        phases=phases,
        total_tasks=total_tasks,
    )
    return ("checklist.md", content)


async def _gen_interfaces(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    modules = _modules_from_state(state)
    agents = _agents_from_state(state)
    decisions = _decisions_from_state(state)

    async with sem:
        interfaces_json = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate module interface contracts as JSON.\n"
                        "Format: [{\"number\": int, \"title\": str, "
                        "\"provider\": str, \"consumers\": str, "
                        "\"language\": str, \"signatures\": str}]\n"
                        "signatures should contain class/function definitions with type hints.\n"
                        "Use Python-style signatures with `...` for body.\n"
                        "Respond with ONLY the JSON array."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Modules: {json.dumps(modules, ensure_ascii=False)}\n"
                        f"Agents: {json.dumps(agents, ensure_ascii=False)}\n"
                        f"Decisions: {json.dumps(decisions, ensure_ascii=False)}"
                    ),
                },
            ],
            purpose="generate_md",
        )

    try:
        cleaned = _strip_code_fences(interfaces_json)
        interface_sections = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        interface_sections = []

    template = env.get_template("interfaces.md.j2")
    content = template.render(
        date=_today(),
        interface_sections=interface_sections,
    )
    return ("interfaces.md", content)


async def _gen_conventions(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    decisions = _decisions_from_state(state)

    async with sem:
        conventions = await llm.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate coding conventions for a project. Return JSON with keys:\n"
                        "language_style, module_rules, error_handling, state_management, "
                        "external_services, frontend_rules, testing_rules, git_format\n"
                        "Each value is a string with Markdown-formatted rules.\n"
                        "Respond with ONLY valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Decisions: {json.dumps(decisions, ensure_ascii=False)}",
                },
            ],
            purpose="generate_md",
        )

    try:
        cleaned = _strip_code_fences(conventions)
        conv_data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        conv_data = {}

    template = env.get_template("conventions.md.j2")
    content = template.render(
        language_style=conv_data.get("language_style", ""),
        module_rules=conv_data.get("module_rules", ""),
        error_handling=conv_data.get("error_handling", ""),
        state_management=conv_data.get("state_management", ""),
        external_services=conv_data.get("external_services", ""),
        frontend_rules=conv_data.get("frontend_rules", ""),
        testing_rules=conv_data.get("testing_rules", ""),
        git_format=conv_data.get("git_format", ""),
    )
    return ("conventions.md", content)


async def _gen_shared_memory(
    state: GenerateGraphState,
    _llm: Any,
    env: jinja2.Environment,
    _sem: asyncio.Semaphore,
) -> tuple[str, str]:
    agents = _agents_from_state(state)
    modules = _modules_from_state(state)
    dep_graph = state.dependency_graph
    decisions = _decisions_from_state(state)

    export_registry = []
    for agent in agents:
        for mod_name in agent.get("modules", []):
            mod = next((m for m in modules if m.get("name") == mod_name), None)
            directory = mod.get("directory", mod_name) if mod else mod_name
            export_registry.append({
                "agent": agent.get("agent_id", ""),
                "path": directory,
                "exports": "(to be filled)",
            })

    dependency_tracking = []
    agent_by_module: dict[str, str] = {}
    for agent in agents:
        for mod_name in agent.get("modules", []):
            agent_by_module[mod_name] = agent.get("agent_id", "")

    for mod_name, deps in dep_graph.items():
        waiting_agent = agent_by_module.get(mod_name, "")
        for dep in deps:
            source_agent = agent_by_module.get(dep, "")
            dependency_tracking.append({
                "waiting": waiting_agent,
                "needs": dep,
                "source": source_agent,
                "checklist": "-",
            })

    decision_log = []
    for d in decisions:
        decision_log.append({
            "topic": d.get("topic", d.get("chosen", "")),
            "rationale": d.get("rationale", d.get("label", "")),
            "scope": "ALL",
        })

    phase_agents: dict[int, list[str]] = {}
    for a in agents:
        p = a.get("phase", 1)
        phase_agents.setdefault(p, []).append(a.get("agent_id", ""))
    first_phase = sorted(phase_agents.keys())[0] if phase_agents else 1
    init_agents = " + ".join(phase_agents.get(first_phase, []))
    init_message = f"Phase {first_phase}: {init_agents} 병렬 작업."

    template = env.get_template("shared-memory.md.j2")
    content = template.render(
        date=_today(),
        project_name=_project_name(state),
        init_message=init_message,
        export_registry=export_registry,
        dependency_tracking=dependency_tracking,
        decision_log=decision_log,
    )
    return ("shared-memory.md", content)


async def _gen_knowledge(
    state: GenerateGraphState,
    _llm: Any,
    env: jinja2.Environment,
    _sem: asyncio.Semaphore,
) -> tuple[str, str]:
    template = env.get_template("knowledge.md.j2")
    content = template.render()
    return ("knowledge.md", content)


async def _gen_errors(
    state: GenerateGraphState,
    _llm: Any,
    env: jinja2.Environment,
    _sem: asyncio.Semaphore,
) -> tuple[str, str]:
    template = env.get_template("errors.md.j2")
    content = template.render()
    return ("errors.md", content)


async def _gen_prompts(
    state: GenerateGraphState,
    llm: Any,
    env: jinja2.Environment,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    agents = _agents_from_state(state)
    modules = _modules_from_state(state)
    decisions = _decisions_from_state(state)

    phase_map: dict[int, list[dict[str, Any]]] = {}
    for agent in agents:
        p = agent.get("phase", 1)
        phase_map.setdefault(p, [])
        phase_map[p].append(agent)

    phases = []
    for phase_num in sorted(phase_map):
        phase_agents = phase_map[phase_num]
        agent_labels = " + ".join(a.get("agent_id", "") for a in phase_agents)

        async with sem:
            prompts_json = await llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate dispatch prompts for coding agents.\n"
                            "Return JSON array: [{\"agent_id\": str, \"persona_name\": str, "
                            "\"prompt_text\": str}]\n"
                            "Each prompt should:\n"
                            "1. State the agent's role\n"
                            "2. List files to read before starting\n"
                            "3. Describe specific tasks for this phase\n"
                            "4. Include completion checklist\n"
                            "Respond with ONLY the JSON array."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Phase {phase_num} agents: "
                            f"{json.dumps(phase_agents, ensure_ascii=False)}\n"
                            f"All modules: {json.dumps(modules, ensure_ascii=False)}\n"
                            f"Decisions: {json.dumps(decisions, ensure_ascii=False)}"
                        ),
                    },
                ],
                purpose="generate_md",
            )

        try:
            cleaned = _strip_code_fences(prompts_json)
            agent_prompts = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            agent_prompts = [
                {
                    "agent_id": a.get("agent_id", ""),
                    "persona_name": a.get("persona_name", ""),
                    "prompt_text": (
                        f"너는 {a.get('agent_id', '')} "
                        f"({a.get('persona_name', '')}) 역할이야.\n시작해줘."
                    ),
                }
                for a in phase_agents
            ]

        phases.append({
            "number": phase_num,
            "title": f"Phase {phase_num}",
            "agent_labels": agent_labels,
            "agent_prompts": agent_prompts,
        })

    template = env.get_template("OPERATION-GUIDE.md.j2")
    content = template.render(
        project_name=_project_name(state),
        phases=phases,
    )
    return ("OPERATION-GUIDE.md", content)


# ============================================================================
# All generators registry
# ============================================================================

_ALL_GENERATORS = [
    _gen_agent_md,
    _gen_persona,
    _gen_plan_md,
    _gen_spec,
    _gen_checklist,
    _gen_interfaces,
    _gen_conventions,
    _gen_shared_memory,
    _gen_knowledge,
    _gen_errors,
    _gen_prompts,
]


@dataclass
class GenerateAllNode(BaseNode[GenerateGraphState, GenerateDeps]):
    """Generate all 11 .vibe/ MD files concurrently."""

    async def run(
        self,
        ctx: GraphRunContext[GenerateGraphState, GenerateDeps],
    ) -> ValidateNode:
        from architect.generate.nodes.validate import ValidateNode

        env = _create_jinja_env()
        sem = asyncio.Semaphore(_MAX_CONCURRENT)
        llm = ctx.deps.llm

        log.info("GenerateAllNode: starting (%d generators)", len(_ALL_GENERATORS))

        results = await asyncio.gather(
            *[gen(ctx.state, llm, env, sem) for gen in _ALL_GENERATORS],
            return_exceptions=True,
        )

        generated: dict[str, str] = {}
        for result in results:
            if isinstance(result, Exception):
                log.warning("GenerateAllNode: generator failed: %s", result)
                continue
            filename, content = result
            generated[filename] = content

        log.info("GenerateAllNode: completed (%d files)", len(generated))

        ctx.state.generated_files = generated
        return ValidateNode()
