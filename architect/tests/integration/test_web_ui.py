"""Web UI E2E tests using FastAPI TestClient.

All LLM calls and engine internals are mocked so no API keys are required.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from architect.core.models import Choice, PlanState
from architect.ui.app import create_app
from architect.ui.schemas import ProgressMessage

# ---------------------------------------------------------------------------
# Mock data factories
# ---------------------------------------------------------------------------


def _choices_state() -> PlanState:
    """PlanState waiting for a user choice."""
    return {
        "user_request": "Build a TODO API",
        "conversation_history": [
            {"role": "user", "content": "Build a TODO API"},
            {
                "role": "assistant",
                "content": "Choose a framework",
                "type": "choices",
                "topic": "tech_stack",
                "choices": [
                    {
                        "id": "A",
                        "label": "FastAPI",
                        "description": "Modern async",
                        "pros": ["Fast"],
                        "cons": ["Newer"],
                        "recommended": True,
                        "reason": "best fit",
                    },
                ],
            },
        ],
        "domain_analysis": {"domain": "web"},
        "decisions": [],
        "open_questions": [],
        "current_step": "waiting_choice",
        "plan_document": "",
        "approved": False,
    }


def _approved_state() -> PlanState:
    """PlanState that is approved and complete."""
    return {
        "user_request": "Build a TODO API",
        "conversation_history": [
            {"role": "user", "content": "Build a TODO API"},
            {"role": "assistant", "content": "Plan finalized."},
        ],
        "domain_analysis": {"domain": "web"},
        "decisions": [
            {
                "topic": "tech_stack",
                "chosen": "A",
                "label": "FastAPI",
                "rationale": "async",
            },
        ],
        "open_questions": [],
        "current_step": "finalized",
        "plan_document": "# TODO API Plan\n\nBuild a REST API with FastAPI.",
        "approved": True,
    }


def _build_mock_plan_engine() -> MagicMock:
    """Build a mock PlanEngine with predictable state transitions."""
    engine = MagicMock()
    engine.start = AsyncMock(return_value=_choices_state())
    engine.respond = AsyncMock(return_value=_approved_state())
    engine.is_complete = lambda s: s.get("approved", False)
    engine.needs_user_input = lambda s: s.get("current_step") in (
        "waiting_choice",
        "wait_approval",
    )
    engine.get_current_choices = lambda s: (
        [Choice(**c) for c in s["conversation_history"][-1]["choices"]]
        if s.get("current_step") == "waiting_choice"
        else None
    )
    engine.get_plan_document = lambda s: s.get("plan_document", "")
    return engine


def _build_mock_execute_engine() -> MagicMock:
    """Build a mock ExecuteEngine with status, diff, tree, and test data."""
    engine = MagicMock()
    engine.run = AsyncMock(return_value={"system_status": "complete"})
    engine.pause = AsyncMock()
    engine.on_progress = MagicMock()
    engine.get_status.return_value = {
        "system_status": "running",
        "current_phase": 1,
        "current_sprint": 1,
        "total_iterations": 3,
        "max_total_iterations": 30,
        "total_phases": 4,
        "phase_status": "running",
        "cost_usd": 0.42,
        "validation_results": [
            {"step": "lint", "passed": True, "message": "ok"},
            {"step": "unit_test", "passed": False, "message": "1 failure"},
        ],
    }
    engine.get_diff.return_value = [
        {"path": "main.py", "status": "A", "diff": "from fastapi import FastAPI\n"},
        {
            "path": "utils.py",
            "status": "M",
            "diff": "-old_line\n+new_line\n context\n",
        },
    ]
    engine.get_file_tree.return_value = ["main.py", "utils.py", "test_main.py"]
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """Create a TestClient with mocked LLMRouter and settings.

    Patches LLMRouter and settings at the app-factory level so ``create_app``
    can run without real API keys. PlanEngine is also patched so that the
    PlanSessionManager creates our controllable mock engine.
    """
    mock_llm_router = MagicMock()
    mock_settings = MagicMock()
    mock_settings.workspace_path = "/tmp/architect-test"

    mock_plan_engine = _build_mock_plan_engine()

    with (
        patch("architect.ui.app.LLMRouter", return_value=mock_llm_router),
        patch("architect.ui.app.settings", mock_settings),
        patch(
            "architect.ui.plan_session_manager.PlanEngine",
            return_value=mock_plan_engine,
        ),
    ):
        app = create_app()
        yield TestClient(app)


@pytest.fixture()
def client_with_job(client: TestClient) -> tuple[TestClient, str]:
    """Return (client, job_id) with a pre-registered execution job.

    Inserts a mock _JobContext directly into the EngineManager so that
    execute/diff/preview routes can find the job without actually launching
    a background task.
    """
    mock_engine = _build_mock_execute_engine()
    queue: asyncio.Queue[ProgressMessage] = asyncio.Queue(maxsize=100)

    # Import _JobContext to construct a realistic context
    from architect.ui.engine_manager import _JobContext

    job_id = "test-job-001"
    ctx = _JobContext(
        engine=mock_engine,
        queue=queue,
        task=None,
        status="running",
        workspace_path="/tmp/architect-test/workspace",
    )
    # Inject directly into the manager's internal dict
    client.app.state.engine_manager._jobs[job_id] = ctx  # type: ignore[union-attr]

    return client, job_id


# ---------------------------------------------------------------------------
# Tests — Health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests — Plan API
# ---------------------------------------------------------------------------


class TestPlanAPI:
    def test_start_plan_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/plan/start",
            json={"user_request": "Build a TODO API"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "plan_id" in data
        assert len(data["plan_id"]) > 0
        assert "first_message" in data

    def test_respond_to_plan(self, client: TestClient) -> None:
        # Start a plan first
        start_resp = client.post(
            "/api/plan/start",
            json={"user_request": "Build a TODO API"},
        )
        plan_id = start_resp.json()["plan_id"]

        resp = client.post(
            f"/api/plan/{plan_id}/respond",
            json={"choice_id": "A"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_get_plan_status(self, client: TestClient) -> None:
        start_resp = client.post(
            "/api/plan/start",
            json={"user_request": "Build a TODO API"},
        )
        plan_id = start_resp.json()["plan_id"]

        resp = client.get(f"/api/plan/{plan_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "step" in data
        assert "decisions_count" in data
        assert "complete" in data
        assert isinstance(data["complete"], bool)

    def test_get_plan_choices(self, client: TestClient) -> None:
        start_resp = client.post(
            "/api/plan/start",
            json={"user_request": "Build a TODO API"},
        )
        plan_id = start_resp.json()["plan_id"]

        resp = client.get(f"/api/plan/{plan_id}/choices")
        assert resp.status_code == 200
        data = resp.json()
        assert "choices" in data
        assert "topic" in data
        # The mock starts in waiting_choice state with one choice
        assert len(data["choices"]) == 1
        assert data["choices"][0]["id"] == "A"

    def test_approve_plan(self, client: TestClient) -> None:
        start_resp = client.post(
            "/api/plan/start",
            json={"user_request": "Build a TODO API"},
        )
        plan_id = start_resp.json()["plan_id"]

        resp = client.post(f"/api/plan/{plan_id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert "plan_document" in data
        assert len(data["plan_document"]) > 0

    def test_plan_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/plan/nonexistent-id/status")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Execute API
# ---------------------------------------------------------------------------


class TestExecuteAPI:
    def test_start_execution_returns_201(self, client: TestClient) -> None:
        with patch.object(
            client.app.state.engine_manager,  # type: ignore[union-attr]
            "start",
            new=AsyncMock(return_value="job-abc-123"),
        ):
            resp = client.post(
                "/api/execute/start",
                json={
                    "plan_id": "some-plan-id",
                    "vibe_files": {"checklist.md": "# Checklist"},
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_id"] == "job-abc-123"

    def test_get_execution_status(
        self, client_with_job: tuple[TestClient, str],
    ) -> None:
        client, job_id = client_with_job
        resp = client.get(f"/api/execute/{job_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_status"] == "running"
        assert data["phase"] == 1
        assert data["sprint"] == 1
        assert 0.0 <= data["progress"] <= 1.0
        assert data["cost"] == pytest.approx(0.42)

    def test_stop_execution(
        self, client_with_job: tuple[TestClient, str],
    ) -> None:
        client, job_id = client_with_job
        resp = client.post(f"/api/execute/{job_id}/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"

    def test_execute_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/execute/nonexistent-id/status")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Diff API
# ---------------------------------------------------------------------------


class TestDiffAPI:
    def test_get_diff(
        self, client_with_job: tuple[TestClient, str],
    ) -> None:
        client, job_id = client_with_job
        resp = client.get(f"/api/diff/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert len(data["files"]) == 2

        added_file = data["files"][0]
        assert added_file["path"] == "main.py"
        assert added_file["status"] == "added"
        assert added_file["old_content"] == ""
        assert "fastapi" in added_file["new_content"].lower()

        modified_file = data["files"][1]
        assert modified_file["path"] == "utils.py"
        assert modified_file["status"] == "modified"

    def test_diff_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/diff/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Preview API
# ---------------------------------------------------------------------------


class TestPreviewAPI:
    def test_get_file_tree(
        self,
        client_with_job: tuple[TestClient, str],
        tmp_path: Any,
    ) -> None:
        client, job_id = client_with_job

        # Create real files in tmp_path so _build_tree can walk the directory
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
        (src_dir / "utils.py").write_text("# utils", encoding="utf-8")

        # Point the job's workspace_path to tmp_path
        ctx = client.app.state.engine_manager._jobs[job_id]  # type: ignore[union-attr]
        ctx.workspace_path = str(tmp_path)

        resp = client.get(f"/api/preview/{job_id}/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "directory"
        assert data["children"] is not None
        # Should contain both a directory ("src") and a file ("main.py")
        names = {child["name"] for child in data["children"]}
        assert "main.py" in names
        assert "src" in names

    def test_get_file_content(
        self,
        client_with_job: tuple[TestClient, str],
        tmp_path: Any,
    ) -> None:
        client, job_id = client_with_job

        # Create a file to read
        (tmp_path / "hello.py").write_text(
            "print('hello world')", encoding="utf-8",
        )
        ctx = client.app.state.engine_manager._jobs[job_id]  # type: ignore[union-attr]
        ctx.workspace_path = str(tmp_path)

        resp = client.get(
            f"/api/preview/{job_id}/file",
            params={"path": "hello.py"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "print('hello world')"
        assert data["language"] == "python"

    def test_get_test_results(
        self, client_with_job: tuple[TestClient, str],
    ) -> None:
        client, job_id = client_with_job
        resp = client.get(f"/api/preview/{job_id}/tests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["passed"] == 1
        assert data["failed"] == 1
        assert len(data["results"]) == 2

    def test_preview_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/preview/nonexistent-id/tree")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — WebSocket
# ---------------------------------------------------------------------------


class TestProgressWebSocket:
    def test_progress_websocket_connection(
        self, client_with_job: tuple[TestClient, str],
    ) -> None:
        client, job_id = client_with_job

        # Pre-load the queue with a progress message and a completion message
        queue = client.app.state.engine_manager.get_queue(job_id)  # type: ignore[union-attr]
        queue.put_nowait(
            ProgressMessage(
                type="node_complete",
                phase=1,
                sprint=1,
                task="plan_sprint",
                status="running",
                message="Sprint planned",
                timestamp="2026-03-12T00:00:00+00:00",
            )
        )
        queue.put_nowait(
            ProgressMessage(
                type="complete",
                phase=1,
                sprint=1,
                task="done",
                status="completed",
                message="Execution complete",
                timestamp="2026-03-12T00:00:01+00:00",
            )
        )

        with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
            first = ws.receive_json()
            assert first["type"] == "node_complete"
            assert first["phase"] == 1
            assert first["message"] == "Sprint planned"

            second = ws.receive_json()
            assert second["type"] == "complete"
            assert second["status"] == "completed"

    def test_progress_websocket_unknown_job(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/progress/nonexistent-id") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"].lower()
