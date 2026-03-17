"""Mock data generators for UI development before real engines are built."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from architect.core.models import Choice
from architect.ui.schemas import (
    DiffFile,
    DiffResponse,
    ExecuteStartResponse,
    ExecuteStatusResponse,
    ExecuteStopResponse,
    FileContentResponse,
    FileTreeNode,
    PlanApproveResponse,
    PlanChoicesResponse,
    PlanRespondResponse,
    PlanStartResponse,
    PlanStatusResponse,
    ProgressMessage,
    TestResult,
    TestResultResponse,
)

# ---------------------------------------------------------------------------
# Internal state to simulate conversation progression
# ---------------------------------------------------------------------------
_plan_step: dict[str, int] = {}

CONVERSATION_STEPS = [
    {
        "message": (
            "I've analyzed your request. This looks like a **Full Stack** web application "
            "with moderate complexity. Let me ask you a few questions to refine the plan.\n\n"
            "First, which backend framework would you prefer?"
        ),
        "topic": "Backend Framework",
        "choices": [
            Choice(
                id="A",
                label="FastAPI",
                description="Modern async Python framework with automatic OpenAPI docs",
                pros=["Async native", "Auto documentation", "Type safety with Pydantic"],
                cons=["Smaller ecosystem than Django"],
                recommended=True,
                reason="Best fit for API-first architectures",
            ),
            Choice(
                id="B",
                label="Django + DRF",
                description="Batteries-included Python framework with REST support",
                pros=["Mature ecosystem", "Built-in admin", "ORM included"],
                cons=["Synchronous by default", "Heavier setup"],
            ),
            Choice(
                id="C",
                label="Express.js",
                description="Minimal Node.js framework for web applications",
                pros=["JavaScript everywhere", "Huge npm ecosystem", "Lightweight"],
                cons=["No built-in structure", "Callback patterns"],
            ),
        ],
    },
    {
        "message": (
            "Great choice! Now let's decide on the database.\n\n"
            "Based on your project requirements, here are the recommended options:"
        ),
        "topic": "Database",
        "choices": [
            Choice(
                id="A",
                label="PostgreSQL",
                description="Advanced open-source relational database",
                pros=["ACID compliant", "JSON support", "Extensible"],
                cons=["More setup than SQLite"],
                recommended=True,
                reason="Best balance of features and reliability",
            ),
            Choice(
                id="B",
                label="MongoDB",
                description="Document-oriented NoSQL database",
                pros=["Flexible schema", "Horizontal scaling", "JSON native"],
                cons=["No ACID by default", "Less suitable for relational data"],
            ),
            Choice(
                id="C",
                label="SQLite",
                description="Embedded relational database",
                pros=["Zero config", "File-based", "Great for prototyping"],
                cons=["No concurrent writes", "Not suitable for production"],
            ),
        ],
    },
    {
        "message": (
            "Excellent! One more question about the frontend approach.\n\n"
            "How would you like to structure the frontend?"
        ),
        "topic": "Frontend Architecture",
        "choices": [
            Choice(
                id="A",
                label="React + TypeScript",
                description="Component-based UI library with type safety",
                pros=["Large ecosystem", "Type safety", "Reusable components"],
                cons=["JSX learning curve"],
                recommended=True,
                reason="Industry standard with excellent tooling",
            ),
            Choice(
                id="B",
                label="Vue 3 + TypeScript",
                description="Progressive framework with Composition API",
                pros=["Gentle learning curve", "Great docs", "Composition API"],
                cons=["Smaller ecosystem than React"],
            ),
            Choice(
                id="C",
                label="Svelte",
                description="Compiler-based framework with minimal runtime",
                pros=["No virtual DOM", "Less boilerplate", "Fast"],
                cons=["Smaller community", "Fewer libraries"],
            ),
        ],
    },
    {
        "message": (
            "All decisions are made! Here's the summary:\n\n"
            "- **Backend**: FastAPI with async handlers\n"
            "- **Database**: PostgreSQL with SQLAlchemy ORM\n"
            "- **Frontend**: React + TypeScript with Tailwind CSS\n"
            "- **Testing**: pytest (backend) + Vitest (frontend)\n\n"
            "The plan document is ready for your review. "
            "Click **Approve & Start** when you're ready to begin code generation."
        ),
        "topic": None,
        "choices": None,
    },
]

MOCK_PLAN_DOCUMENT = """# Project Plan

## Architecture Overview
- **Type**: Full Stack Web Application
- **Backend**: FastAPI (Python 3.12+)
- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **Database**: PostgreSQL 16 with SQLAlchemy 2.0
- **Testing**: pytest + Vitest

## Modules
1. **auth** — User authentication (JWT + OAuth2)
2. **api** — REST API endpoints
3. **models** — Database models and migrations
4. **frontend** — React SPA with routing
5. **shared** — Shared types and utilities

## Agent Assignments
| Agent | Modules | Phase |
|-------|---------|-------|
| Agent-1 | auth, models | 1 |
| Agent-2 | api | 2 |
| Agent-3 | frontend | 2 |
| Agent-4 | shared, integration | 3 |

## Estimated Complexity
- **Files**: ~45
- **Sprints**: 3
- **Estimated Cost**: $2.50 USD
"""


# ============================================================================
# Plan mock functions
# ============================================================================


def mock_plan_start(user_request: str) -> tuple[str, PlanStartResponse]:
    plan_id = str(uuid.uuid4())
    _plan_step[plan_id] = 0
    return plan_id, PlanStartResponse(
        plan_id=plan_id,
        first_message=(
            f"Welcome to ARCHITECT Plan Mode!\n\n"
            f"I received your request: *\"{user_request}\"*\n\n"
            f"Let me analyze this and guide you through the planning process."
        ),
    )


def mock_plan_respond(plan_id: str, message: str) -> PlanRespondResponse:
    step = _plan_step.get(plan_id, 0)
    if step >= len(CONVERSATION_STEPS):
        step = len(CONVERSATION_STEPS) - 1
    data = CONVERSATION_STEPS[step]
    _plan_step[plan_id] = step + 1
    return PlanRespondResponse(
        message=data["message"],
        choices=data["choices"],
    )


def mock_plan_status(plan_id: str) -> PlanStatusResponse:
    step = _plan_step.get(plan_id, 0)
    total = len(CONVERSATION_STEPS)
    return PlanStatusResponse(
        step=f"Step {step}/{total}",
        decisions_count=min(step, total - 1),
        complete=step >= total,
    )


def mock_plan_choices(plan_id: str) -> PlanChoicesResponse:
    step = _plan_step.get(plan_id, 0)
    if step < len(CONVERSATION_STEPS) and CONVERSATION_STEPS[step].get("choices"):
        data = CONVERSATION_STEPS[step]
        return PlanChoicesResponse(topic=data["topic"], choices=data["choices"])
    return PlanChoicesResponse(topic="No pending choices", choices=[])


def mock_plan_approve() -> PlanApproveResponse:
    return PlanApproveResponse(plan_document=MOCK_PLAN_DOCUMENT)


# ============================================================================
# Execute mock functions
# ============================================================================


def mock_execute_start(plan_id: str) -> ExecuteStartResponse:
    return ExecuteStartResponse(job_id=str(uuid.uuid4()))


def mock_execute_stop() -> ExecuteStopResponse:
    return ExecuteStopResponse(status="stopped")


def mock_execute_status() -> ExecuteStatusResponse:
    return ExecuteStatusResponse(phase=2, sprint=1, progress=0.35, cost=1.24)


# ============================================================================
# Diff mock functions
# ============================================================================


def mock_diff() -> DiffResponse:
    return DiffResponse(
        files=[
            DiffFile(
                path="src/api/routes.py",
                old_content="",
                new_content=(
                    'from fastapi import APIRouter\n\n'
                    'router = APIRouter()\n\n\n'
                    '@router.get("/health")\n'
                    'async def health():\n'
                    '    return {"status": "ok"}\n'
                ),
                status="added",
            ),
            DiffFile(
                path="src/config.py",
                old_content=(
                    'DATABASE_URL = "sqlite:///dev.db"\n'
                    'DEBUG = True\n'
                ),
                new_content=(
                    'DATABASE_URL = "postgresql://localhost/myapp"\n'
                    'DEBUG = True\n'
                    'REDIS_URL = "redis://localhost:6379"\n'
                ),
                status="modified",
            ),
            DiffFile(
                path="src/legacy/old_handler.py",
                old_content=(
                    'def handle_request(req):\n'
                    '    """Legacy handler — replaced by FastAPI router."""\n'
                    '    return {"ok": True}\n'
                ),
                new_content="",
                status="deleted",
            ),
        ]
    )


# ============================================================================
# Preview mock functions
# ============================================================================


def mock_file_tree() -> FileTreeNode:
    return FileTreeNode(
        name="project",
        type="directory",
        path=".",
        children=[
            FileTreeNode(
                name="src",
                type="directory",
                path="src",
                children=[
                    FileTreeNode(name="__init__.py", type="file", path="src/__init__.py"),
                    FileTreeNode(name="main.py", type="file", path="src/main.py"),
                    FileTreeNode(name="config.py", type="file", path="src/config.py"),
                    FileTreeNode(
                        name="api",
                        type="directory",
                        path="src/api",
                        children=[
                            FileTreeNode(
                                name="__init__.py", type="file", path="src/api/__init__.py"
                            ),
                            FileTreeNode(
                                name="routes.py", type="file", path="src/api/routes.py"
                            ),
                        ],
                    ),
                    FileTreeNode(
                        name="models",
                        type="directory",
                        path="src/models",
                        children=[
                            FileTreeNode(
                                name="__init__.py", type="file", path="src/models/__init__.py"
                            ),
                            FileTreeNode(name="user.py", type="file", path="src/models/user.py"),
                        ],
                    ),
                ],
            ),
            FileTreeNode(
                name="tests",
                type="directory",
                path="tests",
                children=[
                    FileTreeNode(
                        name="test_routes.py", type="file", path="tests/test_routes.py"
                    ),
                    FileTreeNode(name="test_models.py", type="file", path="tests/test_models.py"),
                ],
            ),
            FileTreeNode(name="pyproject.toml", type="file", path="pyproject.toml"),
            FileTreeNode(name="README.md", type="file", path="README.md"),
        ],
    )


_MOCK_FILES: dict[str, tuple[str, str]] = {
    "src/main.py": (
        "python",
        (
            '"""Application entry point."""\n\n'
            "from fastapi import FastAPI\n"
            "from src.api.routes import router\n\n"
            'app = FastAPI(title="MyApp", version="1.0.0")\n'
            'app.include_router(router, prefix="/api")\n'
        ),
    ),
    "src/config.py": (
        "python",
        (
            'DATABASE_URL = "postgresql://localhost/myapp"\n'
            "DEBUG = True\n"
            'REDIS_URL = "redis://localhost:6379"\n'
        ),
    ),
    "src/api/routes.py": (
        "python",
        (
            "from fastapi import APIRouter\n\n"
            "router = APIRouter()\n\n\n"
            '@router.get("/health")\n'
            "async def health():\n"
            '    return {"status": "ok"}\n'
        ),
    ),
    "src/models/user.py": (
        "python",
        (
            "from sqlalchemy import Column, Integer, String\n"
            "from sqlalchemy.orm import DeclarativeBase\n\n\n"
            "class Base(DeclarativeBase):\n"
            "    pass\n\n\n"
            "class User(Base):\n"
            '    __tablename__ = "users"\n\n'
            "    id = Column(Integer, primary_key=True)\n"
            "    username = Column(String(50), unique=True, nullable=False)\n"
            "    email = Column(String(255), unique=True, nullable=False)\n"
        ),
    ),
}


def mock_file_content(path: str) -> FileContentResponse:
    if path in _MOCK_FILES:
        lang, content = _MOCK_FILES[path]
        return FileContentResponse(content=content, language=lang)
    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
        ".js": "javascript",
        ".json": "json",
        ".toml": "toml",
        ".md": "markdown",
    }
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    lang = ext_map.get(ext, "plaintext")
    return FileContentResponse(content=f"# Content of {path}\n", language=lang)


def mock_test_results() -> TestResultResponse:
    results = [
        TestResult(name="test_health_endpoint", passed=True, output="OK"),
        TestResult(name="test_user_creation", passed=True, output="OK"),
        TestResult(name="test_user_login", passed=True, output="OK"),
        TestResult(name="test_user_duplicate_email", passed=True, output="OK"),
        TestResult(name="test_api_auth_required", passed=True, output="OK"),
        TestResult(name="test_database_connection", passed=True, output="OK"),
        TestResult(
            name="test_user_deletion",
            passed=False,
            output="AssertionError: Expected status 204, got 404",
        ),
        TestResult(
            name="test_concurrent_writes",
            passed=False,
            output="TimeoutError: Database lock timeout after 5s",
        ),
    ]
    passed = sum(1 for r in results if r.passed)
    return TestResultResponse(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


# ============================================================================
# WebSocket mock: progress stream
# ============================================================================

_PROGRESS_EVENTS = [
    ("progress", 1, 1, "plan_parse", "running", "Parsing plan document..."),
    ("progress", 1, 1, "plan_parse", "completed", "Plan parsed: 5 modules, 3 agents"),
    ("progress", 2, 1, "code_generation", "running", "Agent-1 generating auth module..."),
    ("progress", 2, 1, "code_generation", "running", "Agent-2 generating api module..."),
    ("progress", 2, 1, "code_generation", "completed", "Auth module: 4 files generated"),
    ("progress", 2, 1, "code_review", "running", "Reviewing auth module (6 dimensions)..."),
    ("progress", 2, 1, "code_review", "completed", "Review passed: score 4.2/5.0"),
    ("progress", 2, 1, "validation", "running", "Running syntax + lint + typecheck..."),
    ("progress", 2, 1, "validation", "completed", "All validations passed"),
    ("progress", 3, 1, "integration", "running", "Running integration tests..."),
    ("progress", 3, 1, "integration", "completed", "6/8 tests passed, 2 failures"),
    ("progress", 3, 2, "fix", "running", "Diagnosing test failures..."),
    ("progress", 3, 2, "fix", "completed", "Applied fix: updated delete endpoint"),
    ("complete", 4, 1, "deliver", "completed", "Project generation complete!"),
]


async def mock_progress_stream() -> AsyncGenerator[ProgressMessage, None]:
    for type_, phase, sprint, task, status, message in _PROGRESS_EVENTS:
        await asyncio.sleep(0.8)
        yield ProgressMessage(
            type=type_,
            phase=phase,
            sprint=sprint,
            task=task,
            status=status,
            message=message,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )
