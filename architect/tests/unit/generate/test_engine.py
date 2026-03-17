"""Unit tests for the GenerateEngine."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from architect.core.exceptions import GenerateError
from architect.core.models import AgentAssignment, ModuleDefinition
from architect.generate.engine import GenerateEngine
from architect.generate.nodes.assign import AssignmentList
from architect.generate.nodes.decompose import ModuleList


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_module_list() -> ModuleList:
    return ModuleList(
        modules=[
            ModuleDefinition(
                name="core",
                description="Core module",
                directory="src/core/",
                dependencies=[],
                estimated_files=3,
            ),
            ModuleDefinition(
                name="api",
                description="API routes",
                directory="src/api/",
                dependencies=["core"],
                estimated_files=5,
            ),
        ]
    )


def _sample_assignment_list() -> AssignmentList:
    return AssignmentList(
        assignments=[
            AgentAssignment(
                agent_id="Agent-A",
                persona_name="Core Architect",
                modules=["core"],
                phase=1,
                can_parallel_with=[],
            ),
            AgentAssignment(
                agent_id="Agent-B",
                persona_name="API Engineer",
                modules=["api"],
                phase=2,
                can_parallel_with=[],
            ),
        ]
    )


def _mock_llm_complete_side_effect(*args: Any, **kwargs: Any) -> str:
    """Return reasonable JSON for various LLM complete calls."""
    messages = kwargs.get("messages", args[0] if args else [])
    system_msg = ""
    for m in messages:
        if m.get("role") == "system":
            system_msg = m.get("content", "")
            break

    if "system overview" in system_msg.lower() or "directory tree" in system_msg.lower():
        return "OVERVIEW:\nA test project.\n\nTREE:\nsrc/core/\nsrc/api/"

    if "persona details" in system_msg.lower():
        return json.dumps([
            {
                "agent_id": "Agent-A",
                "persona_name": "Core Architect",
                "instructions": "Build core.",
                "forbidden": ["api/ 수정 금지"],
                "scope": "src/core/",
                "knowledge": ["Python docs"],
                "tools": ["pytest"],
            },
            {
                "agent_id": "Agent-B",
                "persona_name": "API Engineer",
                "instructions": "Build API.",
                "forbidden": ["core/ 수정 금지"],
                "scope": "src/api/",
                "knowledge": ["FastAPI docs"],
                "tools": ["pytest"],
            },
        ])

    if "phased implementation plan" in system_msg.lower():
        return json.dumps([{
            "number": 1,
            "title": "Foundation",
            "agent_labels": "Agent-A",
            "description": "Build core",
            "tasks": [
                {"number": 1, "description": "Build core models", "agent": "Agent-A", "dependencies": "-", "priority": "HIGH"},
            ],
        }])

    if "technical specification" in system_msg.lower():
        return "Technical specification section content."

    if "task checklist" in system_msg.lower():
        return json.dumps([{
            "number": 1,
            "title": "Foundation",
            "tasks": [
                {"number": 1, "description": "Build core models", "agent": "A", "notes": ""},
            ],
        }])

    if "interface contracts" in system_msg.lower():
        return json.dumps([{
            "number": 1,
            "title": "Core Service",
            "provider": "Agent-A",
            "consumers": "Agent-B",
            "language": "python",
            "signatures": "class CoreService:\n    def get_data(self) -> dict: ...",
        }])

    if "coding conventions" in system_msg.lower():
        return json.dumps({
            "language_style": "Python 3.12+",
            "module_rules": "No circular imports",
            "error_handling": "Use exceptions",
            "state_management": "TypedDict",
            "external_services": "Via router",
            "frontend_rules": "N/A",
            "testing_rules": "pytest",
            "git_format": "feat(scope): message",
        })

    if "dispatch prompts" in system_msg.lower():
        return json.dumps([{
            "agent_id": "Agent-A",
            "persona_name": "Core Architect",
            "prompt_text": "Build the core module.\napi/ 수정 금지",
        }])

    return "Generated content."


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_generate_produces_all_files() -> None:
    """Full pipeline should produce 11 files."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(
        side_effect=[_sample_module_list(), _sample_assignment_list()]
    )
    mock_llm.complete = AsyncMock(side_effect=_mock_llm_complete_side_effect)

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GenerateEngine(mock_llm)
        files = await engine.generate(
            plan_document="# Test Project\n\nBuild a REST API.",
            decisions=[{"topic": "language", "chosen": "Python", "label": "Python", "rationale": "default"}],
            output_path=tmpdir,
        )

    assert len(files) == 11
    expected = {
        "agent.md", "persona.md", "plan.md", "spec.md",
        "checklist.md", "interfaces.md", "conventions.md",
        "shared-memory.md", "knowledge.md", "errors.md",
        "OPERATION-GUIDE.md",
    }
    assert set(files.keys()) == expected


@pytest.mark.asyncio()
async def test_generate_writes_files_to_disk() -> None:
    """Files should be written to output_path/.vibe/."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(
        side_effect=[_sample_module_list(), _sample_assignment_list()]
    )
    mock_llm.complete = AsyncMock(side_effect=_mock_llm_complete_side_effect)

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GenerateEngine(mock_llm)
        await engine.generate(
            plan_document="# Test\n\nBuild something.",
            decisions=[],
            output_path=tmpdir,
        )

        vibe_dir = os.path.join(tmpdir, ".vibe")
        assert os.path.isdir(vibe_dir)
        assert os.path.isfile(os.path.join(vibe_dir, "agent.md"))
        assert os.path.isfile(os.path.join(vibe_dir, "spec.md"))


@pytest.mark.asyncio()
async def test_generate_empty_plan_raises() -> None:
    """Empty plan should raise GenerateError."""
    mock_llm = AsyncMock()
    engine = GenerateEngine(mock_llm)

    with pytest.raises(GenerateError):
        await engine.generate(
            plan_document="",
            decisions=[],
            output_path="/tmp/test",
        )


@pytest.mark.asyncio()
async def test_generate_retry_on_validation_failure() -> None:
    """Engine should retry when validation finds errors, up to max retries."""
    mock_llm = AsyncMock()

    # First call: decompose, second: assign
    mock_llm.complete_structured = AsyncMock(
        side_effect=[_sample_module_list(), _sample_assignment_list()]
    )
    mock_llm.complete = AsyncMock(side_effect=_mock_llm_complete_side_effect)

    call_count = {"validate": 0}
    original_validate = "architect.generate.nodes.validate.validate_coherence"

    async def mock_validate(state: Any) -> dict[str, Any]:
        call_count["validate"] += 1
        if call_count["validate"] == 1:
            return {"validation_errors": ["test error"], "retry_count": 1}
        return {"validation_errors": [], "retry_count": 1}

    with patch(original_validate, side_effect=mock_validate):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GenerateEngine(mock_llm)
            files = await engine.generate(
                plan_document="# Test\n\nBuild something.",
                decisions=[],
                output_path=tmpdir,
            )

    # Should have generated files despite retry
    assert len(files) > 0
