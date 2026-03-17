# OPERATION-GUIDE.md — Agent Dispatch Prompts

---

## Phase 1: Foundation (Agent-A + Agent-L 동시)

### [>>] Agent-A: Core Architect

```
너는 ARCHITECT 프로젝트의 Agent-A (Core Architect) 역할이야.

## 프로젝트
자율 멀티-에이전트 코딩 오케스트레이션 시스템을 만들고 있어.
사용자가 Plan Mode에서 대화로 명세를 확정하면, 시스템이 자율적으로
여러 코딩 에이전트를 운용해서 실제 동작하는 코드를 생성하는 도구야.

## 작업 전 읽을 파일 (순서대로)
1. .vibe/agent.md
2. .vibe/checklist.md — #1~#6 확인
3. .vibe/persona.md — "Agent-A" 섹션
4. .vibe/spec.md — 1절 Core Models, 2절 State Definitions
5. .vibe/interfaces.md
6. .vibe/conventions.md

## 이번 작업
P1-1 (Core Models & Config) + P1-2 (CLI):
1. pyproject.toml — spec.md 의존성 기반
2. src/architect/core/models.py — spec.md 1절의 전체 Pydantic 모델 구현
3. src/architect/core/exceptions.py — ArchitectBaseError + 하위 계층
4. src/architect/core/logging.py — structlog 설정
5. src/architect/config.py — Pydantic Settings (LLM keys, budget, paths)
6. src/architect/main.py — typer CLI: plan, run, status, serve 명령

## 완료 후
1. checklist.md #1~#6 [DONE] 처리
2. shared-memory.md EXPORT: core/models.py 주요 모델 목록, import 경로

시작해줘.
```

### [>>] Agent-L: LLM Specialist

```
너는 ARCHITECT 프로젝트의 Agent-L (LLM Specialist) 역할이야.

## 프로젝트
자율 멀티-에이전트 코딩 시스템. 모든 Engine이 LLM을 호출할 때
너가 만든 LLMRouter를 통해서만 접근해.

## 작업 전 읽을 파일
1. .vibe/agent.md
2. .vibe/checklist.md — #7~#9
3. .vibe/persona.md — "Agent-L"
4. .vibe/spec.md — 3절 LLM Configuration
5. .vibe/interfaces.md — 1절 LLM Service
6. .vibe/conventions.md

## 이번 작업
P1-2 (LLM Router):
1. src/architect/llm/router.py
   - interfaces.md 1절 LLMRouter 인터페이스 정확히 구현
   - LiteLLM acompletion() 래핑
   - purpose별 모델 자동 선택 (spec.md 3절 PURPOSE_MODEL_MAP)
   - 폴백 체인 (spec.md 3절 FALLBACK_CHAINS)
   - complete_structured(): Pydantic 모델 직접 반환
   - 재시도: 3회, exponential backoff (1s, 2s, 4s)
2. src/architect/llm/models.py — PURPOSE_MODEL_MAP, FALLBACK_CHAINS 설정
3. src/architect/llm/cost_tracker.py — 토큰/비용 추적, budget check
4. src/architect/llm/__init__.py — LLMRouter, CostTracker export

## 완료 후
1. checklist.md #7~#9 [DONE]
2. shared-memory.md EXPORT:
   - import: from src.architect.llm import LLMRouter, CostTracker
   - 초기화: router = LLMRouter(config)
   - 호출: await router.complete_structured(messages, Model, purpose="...")
   - purpose 값 목록

시작해줘.
```

---

## Phase 2: Engines + UI (Agent-P, Agent-G, Agent-U 동시)

### [>>] Agent-P: Plan Engineer

```
너는 ARCHITECT 프로젝트의 Agent-P (Plan Engineer) 역할이야.

## 작업 전 읽을 파일
1. .vibe/checklist.md — #10~#17
2. .vibe/shared-memory.md — Agent-A, Agent-L EXPORT 확인
3. .vibe/persona.md — "Agent-P"
4. .vibe/spec.md — 4절 Plan Engine Design
5. .vibe/interfaces.md — 2절 PlanEngine

## 이번 작업
P2-1 (Plan Engine 전체):
1. plan/states.py — PlanState TypedDict
2. plan/nodes/analyze.py
   - 사용자 요구사항 -> LLM -> DomainAnalysis
   - purpose="plan_analysis"
3. plan/nodes/choices.py
   - 다음 결정 주제에 대해 2-4개 Choice 생성
   - purpose="plan_choices"
4. plan/nodes/refine.py
   - 사용자 선택을 Decision으로 변환, PlanState 업데이트
5. plan/nodes/finalize.py
   - 전체 decisions + domain_analysis -> Plan 문서 Markdown 생성
6. plan/prompts/ (analyst.py, architect.py, choice_generator.py)
7. plan/engine.py
   - StateGraph 조립
   - interrupt_before on wait_user_input, wait_approval
   - spec.md 4절 플로우 정확히 구현
8. tests/unit/plan/ (LLM mock 사용)

## 완료 후
1. checklist.md #10~#17 [DONE]
2. shared-memory.md EXPORT: PlanEngine 초기화 + 사용법

시작해줘.
```

### [>>] Agent-G: Generate Engineer

```
너는 ARCHITECT 프로젝트의 Agent-G (Generate Engineer) 역할이야.

## 작업 전 읽을 파일
1. .vibe/checklist.md — #18~#25
2. .vibe/shared-memory.md — Agent-A, Agent-L EXPORT
3. .vibe/persona.md — "Agent-G"
4. .vibe/spec.md — 5절 Generate Engine Design
5. .vibe/interfaces.md — 3절 GenerateEngine
6. 현 프로젝트의 .vibe/ 파일 전체 (생성 결과의 참조 예시)

## 이번 작업
P2-2 (Generate Engine 전체):
1. generate/states.py
2. generate/nodes/decompose.py — Plan 문서 -> ModuleDefinition 목록
3. generate/nodes/assign.py — 모듈 -> AgentAssignment + dependency_graph
4. generate/nodes/gen_agent_md.py ~ gen_prompts.py (11개 생성 노드)
   - 각 노드는 Jinja2 템플릿 + LLM으로 내용 채움
   - purpose="generate_md"
5. generate/nodes/validate.py — 파일 간 교차 참조 정합성 검증
6. generate/engine.py — StateGraph
7. generate/templates/ — Jinja2 기본 템플릿 10개
   - 현 .vibe/ 파일 구조를 템플릿화
8. tests/unit/generate/

## 핵심
- 현재 .vibe/ 파일들 자체가 Generate Engine이 만들어야 할 출력의 예시야
- 템플릿의 변수 부분만 LLM이 채우고, 구조는 Jinja2로 고정

## 완료 후
1. checklist.md #18~#25 [DONE]
2. shared-memory.md EXPORT: GenerateEngine 사용법

시작해줘.
```

### [>>] Agent-U: UI Engineer

```
너는 ARCHITECT 프로젝트의 Agent-U (UI Engineer) 역할이야.

## 작업 전 읽을 파일
1. .vibe/checklist.md — #26~#35
2. .vibe/persona.md — "Agent-U"
3. .vibe/spec.md — 10절 UI Specification
4. .vibe/interfaces.md — 5절 UI Backend

## 이번 작업
P2-3 (UI Foundation):

Backend:
1. ui/app.py — FastAPI + CORS + WebSocket mount
2. ui/routes/plan.py — POST /api/plan/start, /respond, GET /status
3. ui/routes/diff.py — GET /api/diff/{job_id}
4. ui/routes/execute.py — POST /api/execute/start, stop, GET status
5. ui/routes/preview.py — GET /api/preview/tree, /file, /tests
6. ui/routes/terminal.py — WebSocket /ws/terminal
7. ui/ws/progress.py — WebSocket /ws/progress

Frontend:
8. frontend/ 초기화: React + TypeScript + Tailwind + Vite
9. PlanPage.tsx — 좌: 채팅, 하단: 선택지 카드, 우: Plan 프리뷰
10. DiffPage.tsx — react-diff-viewer unified diff
11. ExecutePage.tsx — 진행률 바 + 로그 + Start/Stop
12. PreviewPage.tsx — 파일 트리 + Monaco Editor 코드 뷰어
13. TerminalPage.tsx — xterm.js WebSocket 터미널
14. components/ — ChatMessage, ChoiceSelector, DiffViewer, FileTree, TerminalEmulator, ProgressTracker

## 완료 후
1. checklist.md #26~#35 [DONE]
2. shared-memory.md EXPORT: 서버 실행법, API 목록

시작해줘.
```

---

## Phase 3: Execute Engine (Agent-E 집중)

### [>>] Agent-E: Execute Engineer

```
너는 ARCHITECT 프로젝트의 Agent-E (Execute Engineer) 역할이야.
ARCHITECT의 가장 핵심 모듈을 구현한다.

## 작업 전 읽을 파일
1. .vibe/checklist.md — #36~#50
2. .vibe/shared-memory.md — 전체 Agent EXPORT 확인 (모두 필요)
3. .vibe/persona.md — "Agent-E" (가장 긴 섹션, 정독)
4. .vibe/spec.md — 6~9절 전체
5. .vibe/interfaces.md — 4절 Execute Engine 전체

## 이번 작업
P3-1 (Execute Engine Core) + P3-2 (Engine 조립):

Supervisor 5역할:
1. supervisor/planner.py — 스프린트 계획 + 리스크 평가
   - 입력: checklist, shared-memory, error_history, agent_performance
   - 출력: sprint_plan {tasks[], blocked[], notes}
   - LLM purpose="supervisor"

2. supervisor/assigner.py — Agent 할당 + 지식 주입
   - knowledge.md에서 관련 지식 검색
   - Agent 프롬프트에 prevention_instructions 주입
   - 출력: assignments[] {agent_id, task_ids, injected_knowledge[]}

3. supervisor/reviewer.py — 코드 리뷰 6차원
   - 인터페이스/컨벤션/아키텍처/구현/보안/테스트
   - purpose="code_review"
   - 출력: ReviewResult (score, passed, issues, revision_instructions)

4. supervisor/diagnostician.py — 에러 근본원인 진단
   - 표면 에러 vs 근본 원인 구분
   - error_history에서 패턴 매칭
   - knowledge.md에서 이전 해결법 검색
   - purpose="diagnose"

5. supervisor/strategist.py — 7가지 전략 결정
   - RETRY | CHANGE_IMPL | SPLIT_TASK | REASSIGN | MODIFY_INTERFACE | ROLLBACK | USER_INPUT
   - purpose="strategize"

Core:
6. dispatcher.py — 프롬프트 조립 (persona + conventions + interfaces + spec + knowledge) + LLM 병렬 호출
   - purpose="code_generation"
   - 출력: AgentCodeOutput (파일 + 테스트 + 메모리 업데이트)

7. validator.py — subprocess로 ruff, mypy, pytest 실행 + 결과 파싱
   - spec.md 8절 VALIDATION_STEPS 구현

8. fixer.py — 에러 분류 + Fix 전략 선택 + Fix Agent 디스패치
   - Diagnostician 결과 기반

9. workspace.py — 파일 I/O + GitPython 자동 커밋/태그/롤백

10. knowledge.py — knowledge.md 파싱/검색/추가/confidence 업데이트

11. execute/prompts/ — agent_system.py, agent_user.py, fix_prompt.py
    - spec.md 7절 프롬프트 구조 참조

12. execute/engine.py — Supervisor Loop StateGraph
    - spec.md 6절의 전체 노드 + 엣지 정의 구현
    - 모든 router function 구현
    - 안전장치: budget_router, iteration check

테스트:
13. tests/unit/execute/ — 각 모듈 단위 테스트
14. tests/integration/ — 간단한 TODO API 프로젝트 자동 생성 E2E

## 완료 후
1. checklist.md #36~#50 [DONE]
2. shared-memory.md EXPORT:
   - Agent-A: ExecuteEngine 초기화법
   - Agent-U: get_status(), get_diff(), on_progress() 사용법

시작해줘.
```

---

## Phase 4: Integration

### [>>] Agent-A + Agent-E: Full Pipeline

```
Phase 4 통합 작업이야. Agent-A와 Agent-E가 협업한다.

## 작업
1. main.py에서 전체 플로우 연결:
   architect plan -> PlanEngine (대화) -> approve
   architect run -> GenerateEngine (MD 생성) -> ExecuteEngine (자율 실행)
   architect serve -> FastAPI UI 시작

2. architect serve 실행 시:
   - 브라우저에서 Plan 대화 시작
   - Plan 완료 -> Diff 확인 -> Start 클릭
   - Execute 자율 실행 (진행률 실시간)
   - 완료 후 Preview에서 결과 확인
   - Terminal에서 직접 명령 가능

3. E2E 테스트: "간단한 TODO REST API를 만들어줘" 입력
   -> Plan 자동 응답 (기술 스택 선택지 등)
   -> Generate (MD 파일 생성)
   -> Execute (코드 자동 생성 + 테스트)
   -> 결과: 동작하는 FastAPI TODO API

## 완료 후
checklist.md #53~#58 [DONE]
```

---

## Session Resume Prompt

```
너는 ARCHITECT 프로젝트의 Agent-[X] 역할이야. 이전 세션을 이어서 해야 해.

읽을 파일:
1. .vibe/checklist.md — [WIP]/[TODO] 중 네 담당 확인
2. .vibe/shared-memory.md — 너에게 온 메시지 확인
3. .vibe/persona.md — 페르소나 재로드
4. .vibe/knowledge.md — 축적된 지식 확인
5. .vibe/errors.md — 이전 에러 확인

이전 작업을 파악하고 이어서 진행해줘.
```
