# ARCHITECT v2 — Supervisor System Design

## PM-Driven Autonomous Development Process

> Version: 2.0.0
> Date: 2026-03-12
> Focus: Supervisor를 실제 개발팀 PM으로 설계

---

# Part 1. 왜 Supervisor가 핵심인가

기존 설계의 문제:
- Execute Engine이 단순 루프(디스패치 -> 검증 -> 재시도)였음
- "에러 3번 반복 시 접근 변경" 같은 판단이 하드코딩된 규칙이었음
- 실제 PM이 하는 일(우선순위 조정, 리소스 재배치, 기술 판단)이 없었음

v2의 핵심 변화:
- Supervisor를 LLM 기반 판단 에이전트로 승격
- 단순 규칙이 아닌, 상황 분석 -> 판단 -> 의사결정의 AI PM
- 실제 개발팀의 프로세스를 정확히 모사

---

# Part 2. 실제 개발팀 프로세스 매핑

## 2.1 사람 개발팀 vs ARCHITECT

```
사람 개발팀                          ARCHITECT 시스템
================================================================
PM이 스프린트 계획                   Supervisor.plan_sprint()
  |                                   |
PM이 개발자에게 티켓 할당            Supervisor.assign_tasks()
  |                                   |
개발자가 코드 작성                   Dispatcher.dispatch_agent()
  |                                   |
개발자가 PR 제출                     Agent가 코드 반환
  |                                   |
시니어가 코드 리뷰                   Reviewer.review_code()        [NEW]
  |                                   |
CI가 테스트 실행                     Validator.run_tests()
  |                                   |
리뷰 코멘트 반영                     Fixer.apply_review()          [NEW]
  |                                   |
QA가 통합 테스트                     Validator.integration_test()
  |                                   |
PM이 스프린트 회고                   Supervisor.retrospective()    [NEW]
  |                                   |
PM이 다음 스프린트 조정              Supervisor.adjust_plan()      [NEW]
================================================================
```

## 2.2 기존에 없던 핵심 프로세스

```
[NEW] Code Review    — Agent 코드를 다른 LLM 페르소나가 리뷰
[NEW] Retrospective  — 매 Phase 끝에 무엇이 잘못됐는지 분석
[NEW] Plan Adjustment — 분석 결과를 바탕으로 다음 Phase 전략 수정
[NEW] Knowledge Accumulation — 에러 패턴을 학습하여 같은 실수 방지
[NEW] Dependency Resolution — 모듈 간 충돌을 자동 중재
[NEW] Risk Assessment — 작업 전에 실패 가능성 사전 평가
```

---

# Part 3. Supervisor 상세 설계

## 3.1 Supervisor의 역할 분리

Supervisor는 단일 LLM 호출이 아니라, 5개 서브 역할로 분리한다.
각 역할은 독립된 프롬프트와 판단 기준을 가진다.

```
Supervisor
  |
  +-- Planner       : 스프린트 계획, 태스크 분해, 우선순위
  +-- Assigner      : Agent 선택, 병렬/순차 결정, 리소스 배분
  +-- Reviewer      : 코드 리뷰, 품질 판단, 아키텍처 일관성
  +-- Diagnostician : 에러 분석, 패턴 탐지, 근본 원인 추론
  +-- Strategist    : 접근 방식 변경, 기술 결정, 에스컬레이션
```

## 3.2 Supervisor State

```python
class SupervisorState(TypedDict):
    # -- Project Context --
    vibe_files: dict[str, str]
    workspace_path: str
    project_description: str

    # -- Sprint State --
    current_phase: int
    current_sprint: int               # Phase 내 스프린트 번호
    sprint_goal: str                  # 이번 스프린트 목표
    sprint_tasks: list[dict]          # 이번 스프린트 태스크
    sprint_results: list[dict]        # 태스크별 결과

    # -- Agent State --
    agent_assignments: list[dict]     # 현재 할당
    agent_performance: dict[str, dict]  # Agent별 성과 이력
    # {"Agent-A": {"success_rate": 0.85, "avg_fix_count": 1.2, "strengths": [...], "weaknesses": [...]}}

    # -- Error Intelligence --
    error_history: list[dict]         # 전체 에러 이력
    error_patterns: list[dict]        # 탐지된 에러 패턴
    # {"pattern": "ImportError in extraction module", "count": 3, "root_cause": "...", "resolution": "..."}
    knowledge_base: list[dict]        # 축적된 해결 지식
    # {"problem": "...", "solution": "...", "context": "...", "success": true}

    # -- Risk State --
    risk_register: list[dict]         # 식별된 리스크
    # {"id": "R1", "description": "...", "probability": "high", "impact": "high", "mitigation": "..."}
    blocked_tasks: list[dict]         # 차단된 태스크

    # -- Metrics --
    phase_metrics: dict               # Phase별 성과 메트릭
    budget_used: float                # LLM 비용
    budget_limit: float
    total_iterations: int
    max_total_iterations: int

    # -- Decision Log --
    decisions: list[dict]             # PM이 내린 모든 결정과 이유
    # {"timestamp": "...", "decision": "...", "rationale": "...", "outcome": "..."}
```

## 3.3 Supervisor Decision Loop (전체 플로우)

```
[Phase Start]
     |
     v
+-- PLAN SPRINT --+
|  Planner가      |
|  checklist 분석 |
|  태스크 분해    |
|  우선순위 결정  |
|  리스크 사전평가|
+---------+-------+
          |
          v
+-- ASSESS RISK --+        <-- [NEW] 작업 전 리스크 평가
|  이전 에러 패턴 |
|  기반 실패 예측 |
|  예방 조치 주입 |
+---------+-------+
          |
          v
+-- ASSIGN TASKS --+
|  Agent 선택      |
|  프롬프트에       |
|  예방 지식 주입  |
|  병렬/순차 결정  |
+---------+--------+
          |
          v
+-- DISPATCH ------+
|  Agent LLM 호출  |
|  (병렬)          |
+---------+--------+
          |
          v
+-- REVIEW CODE ---+        <-- [NEW] 코드 리뷰
|  아키텍처 일관성 |
|  인터페이스 준수 |
|  코딩 컨벤션     |
|  보안 취약점     |
|  성능 우려사항   |
+---------+--------+
          |
     +----+----+
     |         |
  [PASS]    [ISSUES]
     |         |
     v         v
  VALIDATE  REVISE -------> DISPATCH (리뷰 코멘트와 함께)
     |
     v
+-- RUN TESTS -----+
|  lint             |
|  type check       |
|  unit test        |
|  import check     |
+---------+---------+
          |
     +----+----+
     |         |
  [PASS]    [FAIL]
     |         |
     |         v
     |   +-- DIAGNOSE ----+   <-- [NEW] 에러 진단
     |   |  에러 분류      |
     |   |  패턴 매칭      |
     |   |  근본 원인 추론 |
     |   |  이전 해결법 검색|
     |   +--------+-------+
     |            |
     |       +----+----+
     |       |         |
     |   [KNOWN]   [UNKNOWN]
     |       |         |
     |       v         v
     |   APPLY      STRATEGIZE    <-- [NEW] 전략 판단
     |   KNOWN      NEW
     |   FIX        APPROACH
     |       |         |
     |       +----+----+
     |            |
     |            v
     |       DISPATCH FIX -------> (루프 시작)
     |
     v
+-- UPDATE STATE ---+
|  checklist 갱신   |
|  shared-memory    |
|  knowledge base   |
+---------+---------+
          |
          v
+-- SPRINT DONE? --+
     |         |
  [YES]     [NO] --> PLAN SPRINT (남은 태스크)
     |
     v
+-- RETROSPECTIVE -+        <-- [NEW] 회고
|  무엇이 잘 됐나  |
|  무엇이 실패했나  |
|  어떤 패턴인가   |
|  다음에 뭘 바꾸나|
+---------+--------+
          |
          v
+-- NEXT PHASE? ---+
     |         |
  [YES]     [DONE]
     |         |
     v         v
  ADJUST     DELIVER
  PLAN
  (Phase+1)
```

---

# Part 4. 각 서브 역할 상세

## 4.1 Planner — 스프린트 계획

```python
PLANNER_SYSTEM_PROMPT = """
You are a senior engineering PM planning a development sprint.

Your input:
- checklist.md: current progress of all tasks
- shared-memory.md: inter-agent messages and blockers
- error_history: past errors and resolutions
- agent_performance: each agent's track record

Your job:
1. Identify which tasks should be in this sprint
2. Determine task priority (considering dependencies)
3. Estimate risk for each task based on error history
4. Decide sprint scope (do not overcommit)

Rules:
- Never assign more than 5 tasks per sprint
- If a task failed 2+ times before, flag it as HIGH RISK
- If a task depends on another incomplete task, mark as BLOCKED
- Prioritize unblocking other agents over new features

Output JSON:
{
    "sprint_number": 3,
    "sprint_goal": "Complete entity extraction pipeline",
    "tasks": [
        {
            "task_id": 37,
            "description": "LLMEntityRelationExtractor wrapper",
            "agent_id": "Agent-C",
            "priority": 1,
            "risk": "medium",
            "risk_reason": "Similar task failed once in sprint 2 due to prompt format",
            "prevention": "Include explicit JSON schema in prompt, add response validation",
            "dependencies": [26],
            "estimated_complexity": "high"
        }
    ],
    "blocked_tasks": [
        {"task_id": 42, "blocked_by": 28, "reason": "Embedder not ready"}
    ],
    "sprint_notes": "Focus on extraction core. Defer entity resolution to next sprint."
}
"""
```

## 4.2 Assigner — Agent 할당 + 예방 지식 주입

```python
ASSIGNER_SYSTEM_PROMPT = """
You are assigning development tasks to AI coding agents.

Your input:
- sprint_tasks: tasks to assign this sprint
- agent_performance: historical performance per agent
- knowledge_base: known problems and solutions
- error_patterns: recurring error patterns

Your job:
1. Match tasks to the most capable agent (based on persona + history)
2. Decide parallel vs sequential execution
3. For each assignment, inject PREVENTION KNOWLEDGE:
   - Known pitfalls for this type of task
   - Solutions that worked before for similar errors
   - Specific instructions to avoid known failure modes

Rules:
- If Agent-X failed a similar task before, include the error + fix in the prompt
- If two agents need each other's output, sequence them (do not parallelize)
- Include relevant knowledge_base entries in agent prompts

Output JSON:
{
    "assignments": [
        {
            "agent_id": "Agent-C",
            "task_ids": [37, 38],
            "execution_order": 1,
            "parallel_group": "group-1",
            "injected_knowledge": [
                "In sprint 2, extraction prompt returned malformed JSON. Solution: add explicit schema in system prompt and wrap response parsing in try/except with retry.",
                "LLMEntityRelationExtractor requires neo4j-graphrag-python >= 1.5.0. Verify import path: from neo4j_graphrag.experimental.components.entity_relation_extractor import LLMEntityRelationExtractor"
            ],
            "prevention_instructions": "Always validate LLM response against Pydantic model before processing. If validation fails, retry with stricter prompt."
        }
    ],
    "execution_plan": [
        {"group": "group-1", "agents": ["Agent-C", "Agent-D"], "parallel": true},
        {"group": "group-2", "agents": ["Agent-E"], "parallel": false, "after": "group-1"}
    ]
}
"""
```

## 4.3 Reviewer — 코드 리뷰

코드가 생성된 후, 테스트를 돌리기 전에 리뷰를 먼저 한다.
사람 팀에서 시니어 개발자가 PR을 리뷰하는 것과 동일.

```python
REVIEWER_SYSTEM_PROMPT = """
You are a senior code reviewer for an enterprise software project.

Your input:
- generated_code: files produced by a coding agent
- interfaces.md: module interface contracts
- conventions.md: coding standards
- spec.md: technical specification
- existing_code: already committed code in the workspace

Review Dimensions (each scored 1-5):

1. INTERFACE COMPLIANCE
   - Do function signatures match interfaces.md exactly?
   - Are return types correct?
   - Are all required methods implemented?

2. CONVENTION ADHERENCE
   - Naming conventions followed?
   - Import order correct?
   - Error handling patterns correct?
   - Type hints present and correct?

3. ARCHITECTURE CONSISTENCY
   - Does the code fit the overall architecture?
   - Are module boundaries respected?
   - Is dependency direction correct (no circular imports)?

4. IMPLEMENTATION QUALITY
   - Is the code actually functional (not placeholder/TODO)?
   - Are edge cases handled?
   - Is error handling meaningful (not bare except)?
   - Are resources properly managed (connections closed, etc.)?

5. SECURITY
   - No hardcoded secrets?
   - Input validation present?
   - SQL/Cypher injection prevention?

6. TESTABILITY
   - Are test files included?
   - Do tests cover the main functionality?
   - Are tests actually testing something (not empty)?

Output JSON:
{
    "overall_score": 4.2,
    "pass": true,                    // true if overall >= 3.5 and no CRITICAL issues
    "dimensions": {
        "interface_compliance": {"score": 5, "issues": []},
        "convention_adherence": {"score": 4, "issues": ["Missing type hint on line 45 of parser.py"]},
        "architecture_consistency": {"score": 4, "issues": []},
        "implementation_quality": {"score": 4, "issues": ["No retry logic in LLM call"]},
        "security": {"score": 5, "issues": []},
        "testability": {"score": 3, "issues": ["test_parse_pdf only tests happy path"]}
    },
    "critical_issues": [],           // Must fix before proceeding
    "suggestions": [                 // Nice to have
        "Add timeout to Neo4j connection",
        "Consider adding integration test for parser factory"
    ],
    "revision_instructions": "Add type hint on line 45. Add error case test for PDF parser."
}
"""
```

리뷰 결과에 따른 분기:

```
Review Score >= 3.5 AND critical_issues = 0:
  → Validation(테스트)으로 진행
  → suggestions는 shared-memory.md에 기록 (다음 스프린트에서 처리)

Review Score < 3.5 OR critical_issues > 0:
  → Agent에게 revision_instructions 전달하여 재생성
  → 최대 2회 리비전 후에도 미달이면 Diagnostician에게 전달
```

## 4.4 Diagnostician — 에러 진단

테스트 실패 시, 단순히 에러 메시지를 Agent에게 전달하는 게 아니라, 먼저 진단한다.

```python
DIAGNOSTICIAN_SYSTEM_PROMPT = """
You are a senior debugging specialist.

Your input:
- error_message: the current error (lint/test/import failure)
- error_history: all past errors in this project
- knowledge_base: known problem-solution pairs
- code_context: the failing code + related modules

Your job:
1. CLASSIFY the error:
   - surface_error: what the error message says
   - root_cause: why it actually happened (may differ from surface)
   - error_category: one of [syntax, import, type, logic, interface_mismatch,
     dependency, environment, design_flaw]

2. PATTERN MATCH against error_history:
   - Is this the same error repeating? If so, how many times?
   - Is this a variation of a previously seen pattern?
   - Did a previous fix introduce this error? (regression)

3. SEARCH knowledge_base for known solutions

4. DETERMINE fix approach:
   - If known solution exists and worked before: recommend it
   - If same error repeated 2x: recommend different approach
   - If same error repeated 3x+: recommend escalation (approach change)
   - If regression detected: identify which fix broke it

Output JSON:
{
    "diagnosis": {
        "surface_error": "ImportError: cannot import name 'LLMRouter' from 'src.llm'",
        "root_cause": "src/llm/__init__.py does not export LLMRouter. Agent-L forgot to update __init__.py",
        "error_category": "import",
        "severity": "blocking",          // blocking | degraded | cosmetic
        "affected_agents": ["Agent-C", "Agent-E"],
        "affected_tasks": [37, 54]
    },
    "pattern_analysis": {
        "seen_before": true,
        "occurrence_count": 2,
        "previous_fixes": [
            {"sprint": 2, "fix": "Added LLMRouter to __init__.py __all__", "worked": false},
            {"sprint": 2, "fix": "Changed import path to direct module", "worked": true}
        ],
        "is_regression": false,
        "pattern_name": "missing_init_export"
    },
    "recommendation": {
        "approach": "apply_known_fix",     // apply_known_fix | new_fix | change_approach | escalate
        "fix_description": "Direct import from module: 'from src.architect.llm.router import LLMRouter' instead of 'from src.architect.llm import LLMRouter'",
        "confidence": 0.9,
        "fallback": "If direct import also fails, check if router.py defines LLMRouter class correctly",
        "prevent_future": "Add import validation step after Agent-L completes: verify all interface exports are importable"
    },
    "knowledge_update": {
        "problem": "LLMRouter not importable from package",
        "solution": "Use direct module import path",
        "context": "When __init__.py __all__ is unreliable",
        "tags": ["import", "init", "llm"]
    }
}
"""
```

## 4.5 Strategist — 전략 판단

에러가 반복되거나 Diagnostician이 "접근 방식 변경" 또는 "에스컬레이션"을 권고했을 때 동작.

```python
STRATEGIST_SYSTEM_PROMPT = """
You are a tech lead making strategic decisions about development approach.

Your input:
- diagnosis: Diagnostician's analysis (including pattern history)
- spec.md: current technical specification
- error_history: full error history
- decisions: all past strategic decisions and their outcomes
- budget_remaining: remaining LLM API budget
- iterations_remaining: remaining retry budget

Your job:
Make one of these strategic decisions:

1. RETRY_WITH_GUIDANCE
   When: First or second failure, clear fix available
   Action: Send specific fix instructions to the agent
   Risk: Low

2. CHANGE_IMPLEMENTATION
   When: Same approach failed 2+ times, or design flaw detected
   Action: Modify spec.md to use different library/pattern/algorithm
   Risk: Medium (may affect other modules)
   Example: "Switch from Docling to Unstructured for PDF parsing"
            "Replace custom entity resolution with neo4j-graphrag built-in"

3. SPLIT_TASK
   When: Task is too complex for single agent pass
   Action: Decompose the task into smaller sub-tasks
   Risk: Low
   Example: "Split entity_extractor.py into: prompt_builder.py, extractor.py, result_parser.py"

4. REASSIGN_AGENT
   When: Agent consistently fails at a specific type of task
   Action: Assign the task to a different agent with injected context
   Risk: Low-Medium

5. MODIFY_INTERFACE
   When: Interface mismatch is the root cause
   Action: Update interfaces.md + notify all dependent agents
   Risk: High (cascading changes)

6. ROLLBACK_AND_RETRY
   When: A fix introduced regressions
   Action: Revert to last known good state, try different fix
   Risk: Medium

7. REQUEST_USER_INPUT
   When: Budget/iteration limit approaching, or fundamental ambiguity
   Action: Pause execution, present situation to user, ask for direction
   Risk: None (but delays delivery)

Output JSON:
{
    "decision": "CHANGE_IMPLEMENTATION",
    "rationale": "Docling PDF parser failed 3 consecutive times with table extraction. Unstructured.io has better table support for this document type.",
    "actions": [
        {
            "type": "update_spec",
            "target": "spec.md section 3.2",
            "change": "Replace Docling with Unstructured partition_pdf for PDF parsing",
            "details": "..."
        },
        {
            "type": "update_interface",
            "target": "interfaces.md section 1",
            "change": "PDFParser.parse() return type unchanged, internal implementation only",
            "affected_agents": ["Agent-B"]
        },
        {
            "type": "invalidate_tasks",
            "task_ids": [14],
            "new_status": "[TODO]",
            "reason": "Implementation approach changed"
        },
        {
            "type": "add_knowledge",
            "entry": {
                "problem": "Docling fails on tables with merged cells",
                "solution": "Use Unstructured partition_pdf with strategy='hi_res'",
                "context": "Enterprise PDF documents with complex tables"
            }
        }
    ],
    "risk_assessment": "Low. Interface unchanged, only internal implementation changes.",
    "estimated_additional_cost": "$0.50",
    "estimated_additional_iterations": 2
}
"""
```

---

# Part 5. Knowledge Accumulation System

## 5.1 Knowledge Base 구조

Supervisor가 프로젝트 진행 중 축적하는 지식:

```python
class KnowledgeEntry(BaseModel):
    id: str
    timestamp: str
    category: str        # "error_fix" | "best_practice" | "pitfall" | "library_note"
    problem: str         # 어떤 문제가 있었는지
    solution: str        # 어떻게 해결했는지
    context: str         # 어떤 상황에서 발생하는지
    tags: list[str]      # 검색용 태그
    confidence: float    # 해결 성공률 (0.0~1.0)
    applied_count: int   # 적용 횟수
    success_count: int   # 성공 횟수
    source_sprint: int
    source_phase: int
```

## 5.2 Knowledge 축적 시점

```
[언제 축적하나]

1. Fix 성공 시:
   Diagnostician의 진단 + 실제 적용한 수정 + 결과
   → knowledge_base에 추가
   → confidence = 1.0 (첫 성공)

2. Fix 실패 시:
   시도한 수정이 실패한 기록
   → confidence 감소
   → "이 방법은 안 됐다"는 음성 지식도 축적

3. Retrospective 시:
   Phase 전체를 분석하여 패턴 추출
   → "이 프로젝트에서 가장 많이 실패한 패턴은 X"
   → "Agent-B는 테이블 파싱에서 70% 성공률"

4. Strategist 결정 시:
   접근 방식 변경 결정 + 이유 + 결과
   → "Docling -> Unstructured 전환 후 성공률 100%"
```

## 5.3 Knowledge 활용 시점

```
[언제 활용하나]

1. Assigner가 Agent 프롬프트 조립 시:
   해당 태스크 관련 knowledge를 검색하여 주입
   "이전에 이런 문제가 있었고 이렇게 해결했으니 참고해"

2. Diagnostician이 에러 분석 시:
   유사 에러의 이전 해결법 검색
   "이 패턴은 전에 X로 해결했고 성공률 90%"

3. Strategist가 전략 결정 시:
   이전 전략 결정의 성공/실패 이력 참조
   "Docling -> Unstructured 전환은 이전 프로젝트에서도 성공"

4. Planner가 리스크 평가 시:
   실패 빈도가 높은 태스크 유형 식별
   "LLM 프롬프트 관련 태스크는 평균 1.5회 재시도 필요"
```

---

# Part 6. Retrospective System

## 6.1 매 Phase 종료 시 자동 회고

```python
RETROSPECTIVE_PROMPT = """
You are conducting a sprint retrospective for an AI development team.

Input:
- phase_number: which phase just completed
- sprint_history: all sprints in this phase
  - tasks attempted, succeeded, failed
  - error types and frequencies
  - fix attempts and outcomes
  - agent performance metrics
- knowledge_base: accumulated knowledge so far
- decisions: strategic decisions made during this phase

Analyze and produce:

1. WHAT WENT WELL
   - Which tasks completed on first try?
   - Which agents performed best?
   - Which knowledge entries were most useful?

2. WHAT WENT WRONG
   - Which tasks required most retries?
   - What were the most common error types?
   - Were there any regressions (fixes that broke other things)?
   - Were there any blocked tasks that could have been prevented?

3. ROOT CAUSE ANALYSIS
   - For recurring errors: what is the systemic cause?
   - For agent failures: is it the prompt, the persona, or the task complexity?
   - For interface mismatches: is the interface definition insufficient?

4. IMPROVEMENT ACTIONS for next phase
   - Specific changes to agent prompts
   - Interface clarifications needed
   - Tasks that should be split or merged
   - Agent assignments that should change

5. METRICS SUMMARY
   - First-pass success rate (tasks that passed on first try)
   - Average fix iterations per task
   - Total cost this phase
   - Time per task

Output JSON:
{
    "phase": 2,
    "metrics": {
        "tasks_total": 16,
        "tasks_first_pass": 11,
        "tasks_with_fixes": 4,
        "tasks_failed": 1,
        "first_pass_rate": 0.69,
        "avg_fix_iterations": 1.8,
        "total_cost_usd": 4.20,
        "total_llm_calls": 34
    },
    "went_well": [
        "Plan engine nodes all passed on first try",
        "Knowledge injection prevented PDF parser repeat failure"
    ],
    "went_wrong": [
        "Entity resolver failed 3 times due to embedding dimension mismatch",
        "Generate engine validate node had interface mismatch with spec.md"
    ],
    "root_causes": [
        {
            "issue": "Embedding dimension mismatch",
            "cause": "spec.md says 3072 but Embedder returns 1536 when using text-embedding-3-small",
            "fix": "Pin embedding model in config, add dimension assertion in Embedder.__init__"
        }
    ],
    "improvements": [
        {
            "action": "Add embedding dimension assertion to Embedder class",
            "target": "spec.md section 3",
            "priority": "high"
        },
        {
            "action": "Split gen_spec.py into gen_spec_models.py and gen_spec_details.py",
            "target": "plan.md P2-2",
            "priority": "medium"
        }
    ],
    "agent_performance": {
        "Agent-P": {"success_rate": 1.0, "note": "Excellent. All tasks first-pass."},
        "Agent-G": {"success_rate": 0.75, "note": "Struggled with validate.py. Interface knowledge was stale."},
        "Agent-C": {"success_rate": 0.5, "note": "Entity resolver needs task splitting."}
    }
}
"""
```

## 6.2 Retrospective 결과의 적용

```
Retrospective 출력
     |
     v
[improvements 각각에 대해]
     |
     +-- priority: high → 즉시 적용
     |     → spec.md 수정
     |     → interfaces.md 수정
     |     → persona.md에 주의사항 추가
     |     → 관련 checklist 항목 재설정
     |
     +-- priority: medium → 다음 Phase 시작 전 적용
     |     → plan.md 수정 (태스크 분할 등)
     |     → shared-memory.md에 기록
     |
     +-- priority: low → knowledge_base에만 기록
           → 향후 유사 프로젝트에서 활용

[agent_performance 반영]
     → Assigner가 다음 Phase에서 Agent 할당 시 참조
     → success_rate < 0.5인 Agent: 해당 유형 태스크 재배치 고려
```

---

# Part 7. 전체 Execute Engine v2 LangGraph

## 7.1 State

```python
class ExecuteStateV2(TypedDict):
    # -- Base --
    workspace_path: str
    vibe_files: dict[str, str]

    # -- Phase/Sprint --
    current_phase: int
    total_phases: int
    current_sprint: int
    sprint_plan: dict                   # Planner 출력
    sprint_tasks: list[dict]
    sprint_results: list[dict]

    # -- Agent --
    assignments: list[dict]             # Assigner 출력
    execution_plan: list[dict]          # 실행 순서
    current_group: int                  # 현재 실행 중인 group
    agent_outputs: dict[str, dict]

    # -- Review --
    review_results: dict                # Reviewer 출력
    revision_count: int                 # 리비전 횟수

    # -- Validation --
    validation_results: list[dict]

    # -- Diagnosis --
    diagnosis: dict                     # Diagnostician 출력
    fix_strategy: dict                  # Strategist 출력

    # -- Knowledge --
    error_history: list[dict]
    error_patterns: list[dict]
    knowledge_base: list[dict]
    agent_performance: dict[str, dict]

    # -- Control --
    iteration: int
    max_sprint_iterations: int          # 스프린트당 최대 (기본 5)
    total_iterations: int
    max_total_iterations: int           # 전체 최대 (기본 30)
    cost_usd: float
    max_cost_usd: float                 # 예산 한도
    phase_status: str
    system_status: str

    # -- Decisions --
    decisions: list[dict]
    retrospective_results: list[dict]
```

## 7.2 LangGraph Node + Edge 정의

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(ExecuteStateV2)

# ===== Nodes =====
workflow.add_node("read_state", read_vibe_files)
workflow.add_node("plan_sprint", supervisor_plan_sprint)
workflow.add_node("assess_risk", supervisor_assess_risk)
workflow.add_node("assign_tasks", supervisor_assign_tasks)
workflow.add_node("dispatch_agents", dispatcher_dispatch)
workflow.add_node("review_code", reviewer_review)
workflow.add_node("revise_code", dispatcher_revise)
workflow.add_node("validate", validator_run)
workflow.add_node("diagnose", diagnostician_analyze)
workflow.add_node("strategize", strategist_decide)
workflow.add_node("apply_fix", fixer_apply)
workflow.add_node("apply_strategy", apply_strategic_change)
workflow.add_node("update_state", update_vibe_and_knowledge)
workflow.add_node("retrospective", supervisor_retrospective)
workflow.add_node("adjust_plan", supervisor_adjust_plan)
workflow.add_node("check_budget", check_budget_and_limits)
workflow.add_node("request_user", request_user_intervention)

# ===== Entry =====
workflow.set_entry_point("read_state")

# ===== Edges =====
workflow.add_edge("read_state", "plan_sprint")
workflow.add_edge("plan_sprint", "assess_risk")
workflow.add_edge("assess_risk", "assign_tasks")
workflow.add_edge("assign_tasks", "dispatch_agents")
workflow.add_edge("dispatch_agents", "review_code")

# Review -> Pass or Revise
workflow.add_conditional_edges("review_code", review_router, {
    "pass": "validate",
    "revise": "revise_code",
    "max_revisions": "validate",  # 리비전 한도 도달 시 그냥 진행
})
workflow.add_edge("revise_code", "review_code")  # 리뷰 재실행

# Validate -> Pass or Diagnose
workflow.add_conditional_edges("validate", validation_router, {
    "all_pass": "update_state",
    "failures": "diagnose",
})

# Diagnose -> Known fix or Strategy needed
workflow.add_conditional_edges("diagnose", diagnosis_router, {
    "known_fix": "apply_fix",
    "needs_strategy": "strategize",
})

workflow.add_edge("apply_fix", "check_budget")

# Strategy -> Various actions
workflow.add_conditional_edges("strategize", strategy_router, {
    "retry": "check_budget",
    "change_implementation": "apply_strategy",
    "split_task": "apply_strategy",
    "reassign": "assign_tasks",
    "modify_interface": "apply_strategy",
    "rollback": "apply_strategy",
    "request_user": "request_user",
})

workflow.add_edge("apply_strategy", "plan_sprint")  # 전략 변경 후 재계획
workflow.add_edge("request_user", END)  # 사용자 개입 요청 시 중단

# Budget check -> Continue or Stop
workflow.add_conditional_edges("check_budget", budget_router, {
    "ok": "dispatch_agents",        # Fix 적용 후 재디스패치
    "limit_reached": "request_user",
})

# Update -> Sprint done or Continue
workflow.add_conditional_edges("update_state", sprint_router, {
    "sprint_incomplete": "plan_sprint",  # 남은 태스크
    "sprint_complete": "retrospective",
})

# Retrospective -> Next phase or Done
workflow.add_edge("retrospective", "adjust_plan")
workflow.add_conditional_edges("adjust_plan", phase_router, {
    "next_phase": "plan_sprint",
    "all_complete": END,
})

app = workflow.compile()
```

## 7.3 Router Functions

```python
def review_router(state: ExecuteStateV2) -> str:
    review = state["review_results"]
    if review["pass"]:
        return "pass"
    if state["revision_count"] >= 2:
        return "max_revisions"
    return "revise"

def validation_router(state: ExecuteStateV2) -> str:
    results = state["validation_results"]
    if all(r["passed"] for r in results):
        return "all_pass"
    return "failures"

def diagnosis_router(state: ExecuteStateV2) -> str:
    diag = state["diagnosis"]
    approach = diag["recommendation"]["approach"]
    if approach in ("apply_known_fix", "new_fix"):
        return "known_fix"
    return "needs_strategy"

def strategy_router(state: ExecuteStateV2) -> str:
    strategy = state["fix_strategy"]
    decision = strategy["decision"].lower()
    mapping = {
        "retry_with_guidance": "retry",
        "change_implementation": "change_implementation",
        "split_task": "split_task",
        "reassign_agent": "reassign",
        "modify_interface": "modify_interface",
        "rollback_and_retry": "rollback",
        "request_user_input": "request_user",
    }
    return mapping.get(decision, "request_user")

def budget_router(state: ExecuteStateV2) -> str:
    if state["cost_usd"] >= state["max_cost_usd"]:
        return "limit_reached"
    if state["total_iterations"] >= state["max_total_iterations"]:
        return "limit_reached"
    return "ok"

def sprint_router(state: ExecuteStateV2) -> str:
    plan = state["sprint_plan"]
    completed = set(state.get("completed_tasks", []))
    remaining = [t for t in plan["tasks"] if t["task_id"] not in completed]
    if remaining:
        return "sprint_incomplete"
    return "sprint_complete"

def phase_router(state: ExecuteStateV2) -> str:
    if state["current_phase"] >= state["total_phases"]:
        return "all_complete"
    return "next_phase"
```

---

# Part 8. MCP + Skills Integration

## 8.1 Execute Engine이 활용하는 MCP 서버

```
Validator가 사용하는 도구:
  - File System MCP: 프로젝트 파일 읽기/쓰기
  - Terminal MCP: ruff, mypy, pytest 실행
  - Git MCP: 커밋, 디프, 롤백

Dispatcher가 사용하는 도구:
  - LLM API (LiteLLM): Agent 코드 생성 호출

Workspace가 사용하는 도구:
  - File System MCP: 디렉토리 생성, 파일 쓰기
  - Git MCP: 자동 커밋, 브랜치 관리

선택적 확장:
  - Docker MCP: 격리된 테스트 환경 (Neo4j testcontainers 등)
  - Browser MCP: 라이브러리 문서 최신 버전 확인
  - NPM/PyPI MCP: 패키지 버전 확인, 호환성 체크
```

## 8.2 Skills Integration

```
Agent 프롬프트에 주입 가능한 Skills:

Code Generation Skills:
  - Python backend (FastAPI, SQLAlchemy, Pydantic)
  - Graph database (Neo4j, Cypher)
  - LLM integration (LangChain, LangGraph, LiteLLM)
  - Testing (pytest, testcontainers)

Document Skills:
  - Markdown generation (MD 파일 생성)
  - Jinja2 template rendering

Analysis Skills:
  - Error pattern analysis
  - Code complexity assessment
  - Dependency graph analysis
```

---

# Part 9. Safety v2

## 9.1 Multi-Layer Safety

```
Layer 1: Budget Guard
  - 매 LLM 호출 후 비용 누적
  - 예산의 80% 소진 시 경고
  - 100% 소진 시 강제 중단 + 현재 상태 저장

Layer 2: Iteration Guard
  - 스프린트당 최대 5회 반복
  - 전체 최대 30회 반복
  - 한도 접근 시 Strategist에게 "효율적으로 마무리" 지시

Layer 3: Regression Guard
  - 매 Fix 후 전체 테스트 재실행
  - 이전에 통과했던 테스트가 실패하면 즉시 플래그
  - 회귀 감지 시 롤백 후 다른 접근

Layer 4: Scope Guard
  - Agent가 담당 디렉토리 외 파일을 생성하면 거부
  - interfaces.md에 없는 함수를 사용하면 경고
  - spec.md와 다른 구현을 하면 Reviewer가 잡음

Layer 5: Quality Guard
  - Phase 완료 조건: 테스트 통과 + 리뷰 점수 3.5+ + lint 통과
  - 하나라도 미달이면 Phase 완료로 넘어가지 않음
  - 3회 Phase 완료 실패 시 사용자 개입 요청
```

## 9.2 Rollback Strategy

```
Git 기반 롤백:
  - 매 성공적인 Sprint 완료 시 git tag (sprint-P{phase}-S{sprint})
  - 롤백 필요 시 해당 tag로 복원
  - 롤백 후 knowledge_base에 "이 접근은 실패함" 기록
  - 새 접근으로 재시도

Selective Rollback:
  - 특정 Agent의 코드만 롤백 가능
  - 다른 Agent의 작업은 보존
  - Git의 파일 단위 checkout 활용
```

---

# Part 10. 예상 성과 (v1 대비 v2)

```
v1 (단순 루프):
  - First-pass success rate: 약 60%
  - 평균 Fix 횟수: 2.5회/태스크
  - 회귀 발생률: 15%
  - 프로젝트 완성도: 70~80%

v2 (PM Supervisor):
  - First-pass success rate: 약 75% (+15%)
    이유: Risk Assessment + Knowledge Injection이 사전에 실패 방지
  - 평균 Fix 횟수: 1.5회/태스크 (-40%)
    이유: Diagnostician이 정확한 근본 원인 제시, 축적된 지식 활용
  - 회귀 발생률: 5% (-10%)
    이유: Code Review가 테스트 전에 문제 포착, Regression Guard
  - 프로젝트 완성도: 85~92% (+10~12%)
    이유: Retrospective + Plan Adjustment가 누적 개선 유도
```
