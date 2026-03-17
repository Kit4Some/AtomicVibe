# spec.md — ARCHITECT Technical Specification

> Version: 2.0.0

---

## 1. Core Models

```python
# src/architect/core/models.py
from pydantic import BaseModel, Field
from typing import TypedDict, Any, Callable
from enum import Enum
from datetime import datetime

# === Plan Engine ===
class Choice(BaseModel):
    id: str                           # "A", "B", "C", "D"
    label: str
    description: str
    pros: list[str]
    cons: list[str]
    recommended: bool = False
    reason: str = ""

class Decision(BaseModel):
    topic: str
    chosen: str
    label: str
    rationale: str

class DomainAnalysis(BaseModel):
    domain: str
    project_type: str                 # "Backend API" | "Frontend" | "Full Stack" | "CLI" | "Library"
    core_features: list[str]
    implied_requirements: list[str]
    complexity: str                   # "small" | "medium" | "large"
    estimated_agents: int
    initial_questions: list[str]

# === Generate Engine ===
class ModuleDefinition(BaseModel):
    name: str
    description: str
    directory: str
    dependencies: list[str] = Field(default_factory=list)
    estimated_files: int = 5

class AgentAssignment(BaseModel):
    agent_id: str
    persona_name: str
    modules: list[str]
    phase: int
    can_parallel_with: list[str] = Field(default_factory=list)

# === Execute Engine ===
class CodeFile(BaseModel):
    path: str
    content: str
    action: str = "create"            # "create" | "replace" | "append"

class TestFile(BaseModel):
    path: str
    content: str

class SharedMemoryUpdate(BaseModel):
    agent_id: str
    type: str                         # "EXPORT" | "INFO" | "REQUEST" | "ALERT"
    target: str
    subject: str
    content: str

class ChecklistUpdate(BaseModel):
    task_number: int
    status: str
    date: str = ""
    notes: str = ""

class AgentCodeOutput(BaseModel):
    files: list[CodeFile]
    tests: list[TestFile] = Field(default_factory=list)
    shared_memory_updates: list[SharedMemoryUpdate] = Field(default_factory=list)
    checklist_updates: list[ChecklistUpdate] = Field(default_factory=list)
    notes: str = ""

class ValidationResult(BaseModel):
    step: str                         # "syntax" | "lint" | "typecheck" | "unit_test" | "integration"
    passed: bool
    errors: list[dict] = Field(default_factory=list)
    output: str = ""

class ReviewResult(BaseModel):
    overall_score: float
    passed: bool                      # overall >= 3.5 AND critical_issues empty
    dimensions: dict[str, dict]
    critical_issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    revision_instructions: str = ""

class DiagnosisResult(BaseModel):
    surface_error: str
    root_cause: str
    error_category: str
    severity: str                     # "blocking" | "degraded" | "cosmetic"
    seen_before: bool
    occurrence_count: int
    recommendation: dict              # approach, fix_description, confidence, fallback

class FixStrategy(BaseModel):
    error_type: str
    strategy: str
    max_retries: int = 3

class KnowledgeEntry(BaseModel):
    id: str = ""
    category: str                     # "error_fix" | "best_practice" | "pitfall" | "library_note"
    problem: str
    solution: str
    context: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    applied_count: int = 0
    success_count: int = 0
```

---

## 2. State Definitions

```python
# Plan
class PlanState(TypedDict):
    user_request: str
    conversation_history: list[dict]
    domain_analysis: dict
    decisions: list[dict]
    open_questions: list[str]
    current_step: str
    plan_document: str
    approved: bool

# Generate
class GenerateState(TypedDict):
    plan_document: str
    decisions: list[dict]
    modules: list[dict]
    agent_assignments: list[dict]
    dependency_graph: dict
    generated_files: dict[str, str]
    validation_errors: list[str]
    project_path: str

# Execute v2 (Supervisor)
class ExecuteStateV2(TypedDict):
    workspace_path: str
    vibe_files: dict[str, str]
    current_phase: int
    total_phases: int
    current_sprint: int
    sprint_plan: dict
    sprint_tasks: list[dict]
    sprint_results: list[dict]
    assignments: list[dict]
    execution_plan: list[dict]
    current_group: int
    agent_outputs: dict[str, dict]
    review_results: dict
    revision_count: int
    validation_results: list[dict]
    diagnosis: dict
    fix_strategy: dict
    error_history: list[dict]
    error_patterns: list[dict]
    knowledge_base: list[dict]
    agent_performance: dict[str, dict]
    risk_register: list[dict]
    iteration: int
    max_sprint_iterations: int        # default 5
    total_iterations: int
    max_total_iterations: int         # default 30
    cost_usd: float
    max_cost_usd: float               # default 50.0
    phase_status: str
    system_status: str
    decisions: list[dict]
    retrospective_results: list[dict]
```

---

## 3. LLM Configuration

```python
PURPOSE_MODEL_MAP = {
    "plan_analysis":    "claude-sonnet-4.6",
    "plan_choices":     "claude-sonnet-4.6",
    "generate_md":      "claude-sonnet-4.6",
    "code_generation":  "claude-sonnet-4.6",
    "code_review":      "claude-sonnet-4.6",
    "fix":              "claude-sonnet-4.6",
    "diagnose":         "claude-sonnet-4.6",
    "supervisor":       "claude-haiku-4.5",
    "strategize":       "claude-sonnet-4.6",
}

FALLBACK_CHAINS = {
    "claude-sonnet-4.6": ["openai/gpt-4o", "deepseek/deepseek-chat"],
    "claude-haiku-4.5": ["openai/gpt-4o-mini"],
}
```

---

## 4. Plan Engine Design

```
StateGraph Nodes:
  analyze_request  -> domain_analysis 생성, initial_questions 추출
  present_choices  -> 다음 결정 주제에 대해 2-4개 선택지 생성
  wait_user_input  -> interrupt_before (사용자 응답 대기)
  refine_spec      -> 사용자 선택을 decisions에 기록, plan 정제
  generate_plan    -> 최종 Plan 문서 Markdown 생성
  wait_approval    -> interrupt_before (사용자 승인 대기)

Edges:
  analyze -> present_choices -> wait_user_input -> refine
  refine -> (질문 남음?) present_choices 또는 generate_plan
  generate_plan -> wait_approval -> (승인) END 또는 (수정) refine

선택지 카테고리 (순서):
  1. 기술 스택 (언어, 프레임워크, DB)
  2. 아키텍처 패턴 (모놀리식/마이크로서비스/서버리스)
  3. 핵심 기능 목록 + 우선순위
  4. 배포 환경
  5. 인증/보안 방식
  6+ 조건부: LLM 모델, 메시지 큐, CI/CD 등
```

---

## 5. Generate Engine Design

```
StateGraph Nodes:
  decompose_modules  -> Plan 분석, 독립 모듈 목록 생성
  assign_agents      -> 모듈별 Agent 할당, 의존 그래프 생성
  gen_* (11개 병렬)  -> 각 .vibe MD 파일 생성
  validate_coherence -> 파일 간 교차 참조 정합성 검증

검증 항목:
  - plan.md의 모든 Task가 checklist.md에 존재
  - persona.md의 Agent가 agent.md의 Agent Map과 일치
  - interfaces.md의 함수 시그니처가 spec.md와 일치
  - checklist의 Agent 할당이 persona.md의 담당과 일치
  불일치 시 -> 해당 파일 재생성 (최대 2회)
```

---

## 6. Execute Engine Design (Supervisor Loop)

```
StateGraph Nodes + Edges:

  read_state -> plan_sprint -> assess_risk -> assign_tasks
  -> dispatch_agents -> review_code
  -> (review pass?) validate : revise_code -> review_code
  -> (validate pass?) update_state : diagnose
  -> (known fix?) apply_fix -> check_budget -> dispatch_agents
     (needs strategy?) strategize
       -> retry: check_budget
       -> change_impl: apply_strategy -> plan_sprint
       -> split_task: apply_strategy -> plan_sprint
       -> reassign: assign_tasks
       -> rollback: apply_strategy -> plan_sprint
       -> request_user: END (pause)
  -> update_state -> (sprint done?) retrospective : plan_sprint
  -> retrospective -> adjust_plan
  -> (next phase?) plan_sprint : END
```

---

## 7. Supervisor 5-Role Prompts (요약)

### Planner
입력: checklist, shared-memory, error_history, agent_performance
출력: sprint_plan {sprint_number, goal, tasks[], blocked[], notes}
핵심: 태스크당 risk 평가, HIGH RISK 태스크 선별, 스프린트 5개 이내

### Assigner
입력: sprint_tasks, agent_performance, knowledge_base
출력: assignments[] {agent_id, task_ids, injected_knowledge[], prevention_instructions}
핵심: 이전 실패 지식을 Agent 프롬프트에 주입

### Reviewer
입력: generated_code, interfaces.md, conventions.md, spec.md
출력: ReviewResult {overall_score, dimensions{}, critical_issues[], revision_instructions}
6차원: 인터페이스 준수, 컨벤션, 아키텍처, 구현 품질, 보안, 테스트
통과 기준: overall >= 3.5 AND critical_issues = 0

### Diagnostician
입력: error_message, error_history, knowledge_base, code_context
출력: DiagnosisResult {root_cause, error_category, pattern, recommendation}
핵심: 표면 에러 vs 근본 원인 구분, 이전 해결법 검색

### Strategist
입력: diagnosis, spec.md, decisions, budget_remaining, iterations_remaining
출력: 7가지 결정 중 택 1 + actions[] + risk_assessment
결정: RETRY | CHANGE_IMPL | SPLIT_TASK | REASSIGN | MODIFY_INTERFACE | ROLLBACK | USER_INPUT

---

## 8. Validation Pipeline

```python
VALIDATION_STEPS = [
    {"name": "syntax",    "cmd": "python3 -m py_compile {file}", "per_file": True},
    {"name": "lint",      "cmd": "ruff check {src} --output-format json", "per_file": False},
    {"name": "typecheck", "cmd": "mypy {src} --ignore-missing-imports", "per_file": False, "optional": True},
    {"name": "unit_test", "cmd": "pytest {tests} -v --tb=short -q", "per_file": False},
    {"name": "integration", "cmd": "pytest tests/integration/ -v", "phase_end_only": True},
]
```

---

## 9. Knowledge System

축적 시점: Fix 성공, Fix 실패, Retrospective, Strategist 결정
활용 시점: Assigner 프롬프트 주입, Diagnostician 검색, Strategist 참조, Planner 리스크 평가

```python
# knowledge.md 파일 포맷 (JSON lines)
{"id": "K001", "category": "error_fix", "problem": "LLMRouter not importable",
 "solution": "Direct import: from src.architect.llm.router import LLMRouter",
 "context": "__init__.py __all__ missing", "tags": ["import", "init"],
 "confidence": 0.9, "applied_count": 3, "success_count": 2}
```

---

## 10. UI Specification

### API Endpoints

```
Plan Mode:
  POST /api/plan/start        {user_request} -> {plan_id, first_message}
  POST /api/plan/respond      {plan_id, user_input} -> {message, choices?}
  GET  /api/plan/{id}/status  -> {step, decisions_count, complete}
  POST /api/plan/{id}/approve -> {plan_document}

Execute Mode:
  POST /api/execute/start     {plan_id} -> {job_id}
  POST /api/execute/stop      {job_id} -> {status}
  GET  /api/execute/{id}/status -> {phase, sprint, progress, cost}

Diff & Preview:
  GET  /api/diff/{job_id}            -> {files: [{path, old, new, status}]}
  GET  /api/preview/{job_id}/tree    -> {tree: [{path, type, size}]}
  GET  /api/preview/{job_id}/file    ?path=... -> {content, language}
  GET  /api/preview/{job_id}/tests   -> {results: [{name, passed, output}]}

WebSocket:
  WS  /ws/progress/{job_id}   -> 실시간 {type, phase, task, status, message}
  WS  /ws/terminal/{job_id}   -> 양방향 pty (xterm.js 연결)
```

### Frontend Pages

```
PlanPage:
  좌측: 채팅 메시지 스트림 (assistant/user 교대)
  하단: 텍스트 입력 또는 선택지 카드 버튼
  우측: Plan 문서 라이브 프리뷰 (Markdown 렌더링)
  하단 고정: [Approve & Start] 버튼 (Plan 완료 시 활성화)

DiffPage:
  좌측: 변경 파일 목록 (파일 트리, 추가/수정/삭제 표시)
  중앙: unified diff 뷰 (react-diff-viewer, 라인별 색상)
  상단: Phase/Sprint 필터

ExecutePage:
  상단: 전체 진행률 바 (Phase 1/4, Sprint 2/3)
  중앙: 실시간 로그 스트림 (Agent 디스패치, 리뷰, 테스트 결과)
  좌측: Agent 상태 카드 (활성/대기/완료)
  하단 고정: [Start] [Pause] [Stop] 버튼
  우측 패널: 비용 추적, 에러 카운트

PreviewPage:
  좌측: 파일 트리 (클릭으로 파일 선택)
  중앙: Monaco Editor (읽기 전용 코드 뷰어, 구문 강조)
  하단: 테스트 결과 요약 (pass/fail 카운트, 실패 목록)

TerminalPage:
  전체화면: xterm.js 터미널 (WebSocket으로 서버 pty 연결)
  상단: 프로젝트 경로 표시
  사용자가 직접 명령어 실행 가능 (git, pytest, ruff 등)
```

---

## 11. Safety Limits

| Guard | Default | Trigger |
|-------|---------|---------|
| Sprint iteration max | 5 | Fix 루프 무한 방지 |
| Total iteration max | 30 | 전체 무한 방지 |
| Cost limit (USD) | 50.0 | LLM 비용 초과 방지 |
| Single file max lines | 500 | 초과 시 분할 지시 |
| Test timeout (sec) | 300 | 테스트 무한 방지 |
| Review revision max | 2 | 리뷰 루프 제한 |
| Regression detected | - | 즉시 롤백 + 다른 접근 |
| Phase fail count | 3 | 사용자 개입 요청 |
