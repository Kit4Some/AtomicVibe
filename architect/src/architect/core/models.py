"""Core Pydantic models, graph states, and dependencies for ARCHITECT."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums
# ============================================================================


class ProjectType(str, Enum):
    BACKEND_API = "Backend API"
    FRONTEND = "Frontend"
    FULL_STACK = "Full Stack"
    CLI = "CLI"
    LIBRARY = "Library"


class Complexity(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class FileAction(str, Enum):
    CREATE = "create"
    REPLACE = "replace"
    APPEND = "append"


class SharedMemoryType(str, Enum):
    EXPORT = "EXPORT"
    INFO = "INFO"
    REQUEST = "REQUEST"
    ALERT = "ALERT"


class ValidationStep(str, Enum):
    SYNTAX = "syntax"
    LINT = "lint"
    TYPECHECK = "typecheck"
    UNIT_TEST = "unit_test"
    INTEGRATION = "integration"


class Severity(str, Enum):
    BLOCKING = "blocking"
    DEGRADED = "degraded"
    COSMETIC = "cosmetic"


class KnowledgeCategory(str, Enum):
    ERROR_FIX = "error_fix"
    BEST_PRACTICE = "best_practice"
    PITFALL = "pitfall"
    LIBRARY_NOTE = "library_note"


# ============================================================================
# Plan Engine Models
# ============================================================================


class Choice(BaseModel):
    """A single choice option presented to the user during Plan Mode."""

    id: str = Field(description='Choice identifier, e.g. "A", "B", "C", "D"')
    label: str
    description: str
    pros: list[str]
    cons: list[str]
    recommended: bool = False
    reason: str = ""


class Decision(BaseModel):
    """A recorded user decision on a topic."""

    topic: str
    chosen: str
    label: str
    rationale: str


class DomainAnalysis(BaseModel):
    """Analysis of the user's project domain and requirements."""

    domain: str
    project_type: str = Field(description="Backend API | Frontend | Full Stack | CLI | Library")
    core_features: list[str]
    implied_requirements: list[str]
    complexity: str = Field(description="small | medium | large")
    estimated_agents: int = Field(ge=1)
    initial_questions: list[str]


# ============================================================================
# Generate Engine Models
# ============================================================================


class ModuleDefinition(BaseModel):
    """Definition of a code module identified during decomposition."""

    name: str
    description: str
    directory: str
    dependencies: list[str] = Field(default_factory=list)
    estimated_files: int = 5


class AgentAssignment(BaseModel):
    """Assignment of an agent to specific modules."""

    agent_id: str
    persona_name: str
    modules: list[str]
    phase: int = Field(ge=1)
    can_parallel_with: list[str] = Field(default_factory=list)


# ============================================================================
# Execute Engine Models
# ============================================================================


class CodeFile(BaseModel):
    """A code file to be written to the workspace."""

    path: str
    content: str
    action: str = "create"


class TestFile(BaseModel):
    """A test file to be written to the workspace."""

    path: str
    content: str


class SharedMemoryUpdate(BaseModel):
    """An update to shared-memory.md for inter-agent communication."""

    agent_id: str
    type: str = Field(description="EXPORT | INFO | REQUEST | ALERT")
    target: str
    subject: str
    content: str


class ChecklistUpdate(BaseModel):
    """An update to a checklist task status."""

    task_number: int = Field(ge=1)
    status: str
    date: str = ""
    notes: str = ""


class AgentCodeOutput(BaseModel):
    """Structured output from a coding agent dispatch."""

    files: list[CodeFile]
    tests: list[TestFile] = Field(default_factory=list)
    shared_memory_updates: list[SharedMemoryUpdate] = Field(default_factory=list)
    checklist_updates: list[ChecklistUpdate] = Field(default_factory=list)
    notes: str = ""


# ============================================================================
# Supervisor Models
# ============================================================================


class ValidationResult(BaseModel):
    """Result of a single validation step."""

    step: str = Field(description="syntax | lint | typecheck | unit_test | integration")
    passed: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    output: str = ""


class ReviewResult(BaseModel):
    """Result of a 6-dimension code review."""

    overall_score: float = Field(ge=0.0, le=5.0)
    passed: bool = False
    dimensions: dict[str, dict[str, Any]]
    critical_issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    revision_instructions: str = ""

    @model_validator(mode="after")
    def _compute_passed(self) -> ReviewResult:
        self.passed = self.overall_score >= 3.5 and len(self.critical_issues) == 0
        return self


class DiagnosisResult(BaseModel):
    """Result of error diagnosis by the Diagnostician."""

    surface_error: str
    root_cause: str
    error_category: str
    severity: str = Field(description="blocking | degraded | cosmetic")
    seen_before: bool
    occurrence_count: int = Field(ge=0)
    recommendation: dict[str, Any] = Field(
        description="Keys: approach, fix_description, confidence, fallback"
    )


class FixStrategy(BaseModel):
    """Strategy for fixing an error."""

    error_type: str
    strategy: str
    max_retries: int = 3


class KnowledgeEntry(BaseModel):
    """An entry in the knowledge base."""

    id: str = ""
    category: str = Field(description="error_fix | best_practice | pitfall | library_note")
    problem: str
    solution: str
    context: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    applied_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)


# ============================================================================
# pydantic-graph Dataclass States
# ============================================================================


@dataclass
class PlanGraphState:
    """Mutable state for the Plan Engine pydantic-graph."""

    user_request: str = ""
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    domain_analysis: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    current_step: str = "analyze"
    plan_document: str = ""
    approved: bool = False

    def to_typed_dict(self) -> PlanState:
        return PlanState(
            user_request=self.user_request,
            conversation_history=self.conversation_history,
            domain_analysis=self.domain_analysis,
            decisions=self.decisions,
            open_questions=self.open_questions,
            current_step=self.current_step,
            plan_document=self.plan_document,
            approved=self.approved,
        )

    @classmethod
    def from_typed_dict(cls, d: PlanState) -> PlanGraphState:
        return cls(**d)


@dataclass
class GenerateGraphState:
    """Mutable state for the Generate Engine pydantic-graph."""

    plan_document: str = ""
    decisions: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    agent_assignments: list[dict[str, Any]] = field(default_factory=list)
    dependency_graph: dict[str, Any] = field(default_factory=dict)
    generated_files: dict[str, str] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    project_path: str = ""
    retry_count: int = 0

    def to_typed_dict(self) -> GenerateState:
        return GenerateState(
            plan_document=self.plan_document,
            decisions=self.decisions,
            modules=self.modules,
            agent_assignments=self.agent_assignments,
            dependency_graph=self.dependency_graph,
            generated_files=self.generated_files,
            validation_errors=self.validation_errors,
            project_path=self.project_path,
            retry_count=self.retry_count,
        )

    @classmethod
    def from_typed_dict(cls, d: GenerateState) -> GenerateGraphState:
        return cls(**d)


@dataclass
class ExecuteGraphState:
    """Mutable state for the Execute Engine pydantic-graph."""

    workspace_path: str = ""
    vibe_files: dict[str, str] = field(default_factory=dict)
    current_phase: int = 1
    total_phases: int = 1
    current_sprint: int = 0
    sprint_plan: dict[str, Any] = field(default_factory=dict)
    sprint_tasks: list[dict[str, Any]] = field(default_factory=list)
    sprint_results: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[dict[str, Any]] = field(default_factory=list)
    execution_plan: list[dict[str, Any]] = field(default_factory=list)
    current_group: int = 0
    agent_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    review_results: dict[str, Any] = field(default_factory=dict)
    revision_count: int = 0
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    diagnosis: dict[str, Any] = field(default_factory=dict)
    fix_strategy: dict[str, Any] = field(default_factory=dict)
    error_history: list[dict[str, Any]] = field(default_factory=list)
    error_patterns: list[dict[str, Any]] = field(default_factory=list)
    knowledge_base: list[dict[str, Any]] = field(default_factory=list)
    agent_performance: dict[str, dict[str, Any]] = field(default_factory=dict)
    risk_register: list[dict[str, Any]] = field(default_factory=list)
    iteration: int = 0
    max_sprint_iterations: int = 5
    total_iterations: int = 0
    max_total_iterations: int = 50
    cost_usd: float = 0.0
    max_cost_usd: float = 10.0
    phase_status: str = "pending"
    system_status: str = "idle"
    decisions: list[dict[str, Any]] = field(default_factory=list)
    retrospective_results: list[dict[str, Any]] = field(default_factory=list)

    def to_typed_dict(self) -> ExecuteStateV2:
        return ExecuteStateV2(
            workspace_path=self.workspace_path,
            vibe_files=self.vibe_files,
            current_phase=self.current_phase,
            total_phases=self.total_phases,
            current_sprint=self.current_sprint,
            sprint_plan=self.sprint_plan,
            sprint_tasks=self.sprint_tasks,
            sprint_results=self.sprint_results,
            assignments=self.assignments,
            execution_plan=self.execution_plan,
            current_group=self.current_group,
            agent_outputs=self.agent_outputs,
            review_results=self.review_results,
            revision_count=self.revision_count,
            validation_results=self.validation_results,
            diagnosis=self.diagnosis,
            fix_strategy=self.fix_strategy,
            error_history=self.error_history,
            error_patterns=self.error_patterns,
            knowledge_base=self.knowledge_base,
            agent_performance=self.agent_performance,
            risk_register=self.risk_register,
            iteration=self.iteration,
            max_sprint_iterations=self.max_sprint_iterations,
            total_iterations=self.total_iterations,
            max_total_iterations=self.max_total_iterations,
            cost_usd=self.cost_usd,
            max_cost_usd=self.max_cost_usd,
            phase_status=self.phase_status,
            system_status=self.system_status,
            decisions=self.decisions,
            retrospective_results=self.retrospective_results,
        )

    @classmethod
    def from_typed_dict(cls, d: ExecuteStateV2) -> ExecuteGraphState:
        return cls(**d)


# ============================================================================
# pydantic-graph Dependencies
# ============================================================================


@dataclass
class PlanDeps:
    """Dependencies injected into Plan Engine graph nodes."""

    llm: Any  # LLMRouter — avoid circular import


@dataclass
class GenerateDeps:
    """Dependencies injected into Generate Engine graph nodes."""

    llm: Any  # LLMRouter


@dataclass
class ExecuteDeps:
    """Dependencies injected into Execute Engine graph nodes."""

    llm: Any  # LLMRouter
    workspace: Any  # Workspace


# ============================================================================
# Legacy TypedDict States (kept for API compatibility)
# ============================================================================


class PlanState(TypedDict):
    """State for the Plan Engine LangGraph."""

    user_request: str
    conversation_history: list[dict[str, Any]]
    domain_analysis: dict[str, Any]
    decisions: list[dict[str, Any]]
    open_questions: list[str]
    current_step: str
    plan_document: str
    approved: bool


class GenerateState(TypedDict):
    """State for the Generate Engine LangGraph."""

    plan_document: str
    decisions: list[dict[str, Any]]
    modules: list[dict[str, Any]]
    agent_assignments: list[dict[str, Any]]
    dependency_graph: dict[str, Any]
    generated_files: dict[str, str]
    validation_errors: list[str]
    project_path: str
    retry_count: int


class ExecuteStateV2(TypedDict):
    """State for the Execute Engine (Supervisor Loop) LangGraph."""

    workspace_path: str
    vibe_files: dict[str, str]
    current_phase: int
    total_phases: int
    current_sprint: int
    sprint_plan: dict[str, Any]
    sprint_tasks: list[dict[str, Any]]
    sprint_results: list[dict[str, Any]]
    assignments: list[dict[str, Any]]
    execution_plan: list[dict[str, Any]]
    current_group: int
    agent_outputs: dict[str, dict[str, Any]]
    review_results: dict[str, Any]
    revision_count: int
    validation_results: list[dict[str, Any]]
    diagnosis: dict[str, Any]
    fix_strategy: dict[str, Any]
    error_history: list[dict[str, Any]]
    error_patterns: list[dict[str, Any]]
    knowledge_base: list[dict[str, Any]]
    agent_performance: dict[str, dict[str, Any]]
    risk_register: list[dict[str, Any]]
    iteration: int
    max_sprint_iterations: int
    total_iterations: int
    max_total_iterations: int
    cost_usd: float
    max_cost_usd: float
    phase_status: str
    system_status: str
    decisions: list[dict[str, Any]]
    retrospective_results: list[dict[str, Any]]
