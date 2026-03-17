"""Tests for core Pydantic models and TypedDict states."""

from __future__ import annotations

from architect.core.models import (
    AgentAssignment,
    AgentCodeOutput,
    ChecklistUpdate,
    Choice,
    CodeFile,
    Decision,
    DiagnosisResult,
    DomainAnalysis,
    ExecuteStateV2,
    FixStrategy,
    GenerateState,
    KnowledgeEntry,
    ModuleDefinition,
    PlanState,
    ReviewResult,
    SharedMemoryUpdate,
    TestFile,
    ValidationResult,
)


class TestChoice:
    def test_create_choice(self) -> None:
        c = Choice(
            id="A",
            label="FastAPI",
            description="Modern async web framework",
            pros=["Fast", "Auto docs"],
            cons=["Newer ecosystem"],
        )
        assert c.id == "A"
        assert c.recommended is False
        assert c.reason == ""

    def test_create_recommended_choice(self) -> None:
        c = Choice(
            id="B",
            label="Django",
            description="Batteries-included framework",
            pros=["Mature"],
            cons=["Sync by default"],
            recommended=True,
            reason="Well-established",
        )
        assert c.recommended is True

    def test_choice_serialization(self) -> None:
        c = Choice(
            id="A", label="X", description="Y", pros=["a"], cons=["b"]
        )
        data = c.model_dump()
        assert data["id"] == "A"
        restored = Choice.model_validate(data)
        assert restored == c


class TestDecision:
    def test_create_decision(self) -> None:
        d = Decision(
            topic="Framework", chosen="A", label="FastAPI", rationale="Async support"
        )
        assert d.topic == "Framework"
        assert d.chosen == "A"


class TestDomainAnalysis:
    def test_create_domain_analysis(self) -> None:
        da = DomainAnalysis(
            domain="E-commerce",
            project_type="Full Stack",
            core_features=["auth", "payments"],
            implied_requirements=["database", "caching"],
            complexity="medium",
            estimated_agents=4,
            initial_questions=["Which payment provider?"],
        )
        assert da.estimated_agents == 4
        assert len(da.core_features) == 2


class TestModuleDefinition:
    def test_create_with_defaults(self) -> None:
        m = ModuleDefinition(
            name="auth", description="Authentication module", directory="src/auth"
        )
        assert m.dependencies == []
        assert m.estimated_files == 5

    def test_create_with_deps(self) -> None:
        m = ModuleDefinition(
            name="api",
            description="API layer",
            directory="src/api",
            dependencies=["auth", "db"],
            estimated_files=10,
        )
        assert len(m.dependencies) == 2


class TestAgentAssignment:
    def test_create_assignment(self) -> None:
        a = AgentAssignment(
            agent_id="Agent-P",
            persona_name="Plan Engineer",
            modules=["plan"],
            phase=2,
            can_parallel_with=["Agent-G"],
        )
        assert a.phase == 2
        assert "Agent-G" in a.can_parallel_with


class TestCodeFile:
    def test_default_action(self) -> None:
        f = CodeFile(path="src/main.py", content="print('hello')")
        assert f.action == "create"


class TestTestFile:
    def test_create_test_file(self) -> None:
        t = TestFile(path="tests/test_main.py", content="def test_x(): pass")
        assert t.path.startswith("tests/")


class TestSharedMemoryUpdate:
    def test_create_update(self) -> None:
        u = SharedMemoryUpdate(
            agent_id="Agent-A",
            type="EXPORT",
            target="ALL",
            subject="Core done",
            content="models.py ready",
        )
        assert u.type == "EXPORT"


class TestChecklistUpdate:
    def test_create_update(self) -> None:
        u = ChecklistUpdate(task_number=1, status="[DONE]", date="2026-03-12")
        assert u.task_number == 1


class TestAgentCodeOutput:
    def test_create_with_defaults(self) -> None:
        out = AgentCodeOutput(
            files=[CodeFile(path="a.py", content="x = 1")]
        )
        assert len(out.files) == 1
        assert out.tests == []
        assert out.shared_memory_updates == []
        assert out.notes == ""

    def test_serialization_roundtrip(self) -> None:
        out = AgentCodeOutput(
            files=[CodeFile(path="a.py", content="x = 1")],
            tests=[TestFile(path="test_a.py", content="assert True")],
            notes="Done",
        )
        data = out.model_dump()
        restored = AgentCodeOutput.model_validate(data)
        assert restored.notes == "Done"
        assert len(restored.files) == 1


class TestValidationResult:
    def test_passed(self) -> None:
        v = ValidationResult(step="syntax", passed=True)
        assert v.errors == []
        assert v.output == ""

    def test_failed(self) -> None:
        v = ValidationResult(
            step="lint",
            passed=False,
            errors=[{"line": 10, "message": "unused import"}],
            output="ruff output here",
        )
        assert not v.passed
        assert len(v.errors) == 1


class TestReviewResult:
    def test_passed_auto_computed(self) -> None:
        r = ReviewResult(
            overall_score=4.0,
            dimensions={"interface": {"score": 4.0}},
        )
        assert r.passed is True

    def test_failed_low_score(self) -> None:
        r = ReviewResult(
            overall_score=2.5,
            dimensions={"interface": {"score": 2.5}},
        )
        assert r.passed is False

    def test_failed_critical_issues(self) -> None:
        r = ReviewResult(
            overall_score=4.5,
            dimensions={"interface": {"score": 4.5}},
            critical_issues=["Missing error handling"],
        )
        assert r.passed is False


class TestDiagnosisResult:
    def test_create(self) -> None:
        d = DiagnosisResult(
            surface_error="ImportError",
            root_cause="Missing __init__.py",
            error_category="import",
            severity="blocking",
            seen_before=False,
            occurrence_count=1,
            recommendation={
                "approach": "add_init",
                "fix_description": "Create __init__.py",
                "confidence": 0.9,
                "fallback": "manual fix",
            },
        )
        assert d.severity == "blocking"
        assert d.recommendation["confidence"] == 0.9


class TestFixStrategy:
    def test_defaults(self) -> None:
        f = FixStrategy(error_type="import", strategy="retry")
        assert f.max_retries == 3


class TestKnowledgeEntry:
    def test_defaults(self) -> None:
        k = KnowledgeEntry(
            category="error_fix",
            problem="Import fails",
            solution="Add __init__.py",
            context="Missing module init",
        )
        assert k.id == ""
        assert k.confidence == 1.0
        assert k.applied_count == 0
        assert k.tags == []


class TestTypedDictStates:
    def test_plan_state_creation(self) -> None:
        state: PlanState = {
            "user_request": "Build a TODO app",
            "conversation_history": [],
            "domain_analysis": {},
            "decisions": [],
            "open_questions": [],
            "current_step": "analyze_request",
            "plan_document": "",
            "approved": False,
        }
        assert state["user_request"] == "Build a TODO app"
        assert state["approved"] is False

    def test_generate_state_creation(self) -> None:
        state: GenerateState = {
            "plan_document": "# Plan",
            "decisions": [],
            "modules": [],
            "agent_assignments": [],
            "dependency_graph": {},
            "generated_files": {},
            "validation_errors": [],
            "project_path": "/tmp/project",
        }
        assert state["project_path"] == "/tmp/project"

    def test_execute_state_creation(self) -> None:
        state: ExecuteStateV2 = {
            "workspace_path": "/tmp/ws",
            "vibe_files": {},
            "current_phase": 1,
            "total_phases": 4,
            "current_sprint": 1,
            "sprint_plan": {},
            "sprint_tasks": [],
            "sprint_results": [],
            "assignments": [],
            "execution_plan": [],
            "current_group": 0,
            "agent_outputs": {},
            "review_results": {},
            "revision_count": 0,
            "validation_results": [],
            "diagnosis": {},
            "fix_strategy": {},
            "error_history": [],
            "error_patterns": [],
            "knowledge_base": [],
            "agent_performance": {},
            "risk_register": [],
            "iteration": 0,
            "max_sprint_iterations": 5,
            "total_iterations": 0,
            "max_total_iterations": 30,
            "cost_usd": 0.0,
            "max_cost_usd": 50.0,
            "phase_status": "pending",
            "system_status": "idle",
            "decisions": [],
            "retrospective_results": [],
        }
        assert state["max_sprint_iterations"] == 5
        assert state["max_cost_usd"] == 50.0
