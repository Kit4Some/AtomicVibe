"""Pydantic response/request models for UI API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from architect.core.models import Choice


# ============================================================================
# Plan API
# ============================================================================


class PlanStartRequest(BaseModel):
    user_request: str = Field(min_length=1)
    mode: str = Field(default="choice", pattern="^(auto|choice)$")


class AutoDecision(BaseModel):
    choice_id: str
    label: str


class PlanStartResponse(BaseModel):
    plan_id: str
    first_message: str
    choices: list[Choice] | None = None
    mode: str = "choice"
    auto_decisions: list[AutoDecision] | None = None
    plan_document: str | None = None
    vibe_files: dict[str, str] | None = None


class PlanRespondRequest(BaseModel):
    message: str = ""
    choice_id: str | None = None


class PlanRespondResponse(BaseModel):
    message: str
    choices: list[Choice] | None = None


class PlanStatusResponse(BaseModel):
    step: str
    decisions_count: int
    complete: bool


class PlanChoicesResponse(BaseModel):
    choices: list[Choice]
    topic: str


class PlanApproveResponse(BaseModel):
    plan_document: str
    vibe_files: dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Execute API
# ============================================================================


class ExecuteStartRequest(BaseModel):
    plan_id: str
    workspace_path: str = ""
    vibe_files: dict[str, str] | None = None


class ExecuteStartResponse(BaseModel):
    job_id: str


class ExecuteStopResponse(BaseModel):
    status: str


class ExecuteStatusResponse(BaseModel):
    phase: int
    sprint: int
    progress: float = Field(ge=0.0, le=1.0)
    cost: float
    system_status: str = "idle"
    phase_status: str = "idle"
    total_phases: int = 4
    total_iterations: int = 0


# ============================================================================
# Diff API
# ============================================================================


class DiffFile(BaseModel):
    path: str
    old_content: str
    new_content: str
    status: str = Field(pattern="^(added|modified|deleted)$")


class DiffResponse(BaseModel):
    files: list[DiffFile]


# ============================================================================
# Preview API
# ============================================================================


class FileTreeNode(BaseModel):
    name: str
    type: str = Field(pattern="^(file|directory)$")
    path: str
    children: list[FileTreeNode] | None = None


class FileContentResponse(BaseModel):
    content: str
    language: str


class TestResult(BaseModel):
    name: str
    passed: bool
    output: str = ""


class TestResultResponse(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[TestResult]


# ============================================================================
# Settings API
# ============================================================================


class SettingsResponse(BaseModel):
    tier: str
    api_key_configured: bool
    max_agents: int


class ApiKeyRequest(BaseModel):
    key: str = Field(min_length=1)


class ApiKeyResponse(BaseModel):
    valid: bool
    message: str


class TierRequest(BaseModel):
    tier: str = Field(pattern="^(low|mid|high|max)$")


class TierResponse(BaseModel):
    tier: str
    max_agents: int


# ============================================================================
# Vibe File API
# ============================================================================


class VibeFile(BaseModel):
    name: str
    path: str
    content: str


class VibeFileListResponse(BaseModel):
    files: list[VibeFile]


class VibeFileSaveRequest(BaseModel):
    content: str


# ============================================================================
# Agent HITL API
# ============================================================================


class AgentMessage(BaseModel):
    role: str = Field(pattern="^(agent|human)$")
    content: str
    timestamp: str = ""


class AgentDetail(BaseModel):
    agent_id: str
    name: str
    persona: str = ""
    task: str = ""
    status: str = "idle"
    modules: list[str] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    agents: list[AgentDetail]


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class AgentMessageResponse(BaseModel):
    message: str


# ============================================================================
# WebSocket
# ============================================================================


class ProgressMessage(BaseModel):
    type: str
    phase: int
    sprint: int
    task: str
    status: str
    message: str
    timestamp: str
