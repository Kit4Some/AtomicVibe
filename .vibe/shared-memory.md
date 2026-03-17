# shared-memory.md — Inter-Agent Communication

---

## Rules
1. 새 메시지는 최상단에 추가
2. Format: `### [날짜] Agent-X -> Target | Type: INFO/EXPORT/REQUEST/ALERT`
3. 처리 완료 시 RESOLVED로 변경 (삭제 금지)
4. EXPORT는 다른 Agent가 재사용할 코드/설정 공유용

---

## Messages

### [2026-03-12] Agent-A+E -> ALL
**Type**: EXPORT
**Subject**: Phase 4 통합 완료
**Content**:
- main.py: skeleton -> 실제 엔진 연결 완료
  - `architect plan "설명"` — PlanEngine 대화 루프 (rich UI, 선택지 테이블, Plan 프리뷰)
  - `architect run --plan-file plan.json` — GenerateEngine + ExecuteEngine 파이프라인
  - `architect status` — 상태 조회
  - `architect serve` — uvicorn + FastAPI (기존)
- CLI integration test: tests/integration/test_cli.py (6 tests)
- Full E2E pipeline test: tests/integration/test_full_e2e.py (2 tests)
- README.md 작성 (설치, CLI 사용법, 아키텍처, 설정)
- 전체 128 tests 통과

---

### [2026-03-12] Agent-E -> ALL
**Type**: EXPORT
**Subject**: Execute Engine 완료 (Supervisor Loop + 지원 모듈 전체)
**Content**:
- 생성된 파일: execute/engine.py, execute/states.py, execute/dispatcher.py, execute/validator.py, execute/fixer.py, execute/workspace.py, execute/knowledge.py, execute/prompts/(agent_system,agent_user,fix_prompt).py, execute/supervisor/(planner,assigner,reviewer,diagnostician,strategist).py, execute/__init__.py
- import 경로:
  `from architect.execute import ExecuteEngine`
- 초기화: `engine = ExecuteEngine(llm_router, workspace_path)`
- 실행: `result = await engine.run(vibe_files)`
  - `vibe_files`: dict[str, str] — checklist.md, shared-memory.md, persona.md, interfaces.md, conventions.md, spec.md
  - Returns: `ExecuteStateV2` — 최종 상태 (system_status, current_phase, current_sprint 등)
- 일시정지/재개: `await engine.pause()` / `result = await engine.resume()`
- 상태 조회: `engine.get_status()` → dict (system_status, current_phase, current_sprint, ...)
- 파일 트리: `engine.get_file_tree()` → list[str]
- Diff: `engine.get_diff()` → list[dict]
- 진행 콜백: `engine.on_progress(callback)` — callback(event: str, data: dict)
- StateGraph: 17노드 + 7라우터 (read_state→plan_sprint→assess_risk→assign_tasks→dispatch_agents→review_code→validate→update_state→retrospective→adjust_plan→END)
- Supervisor 5역할: planner, assigner, reviewer, diagnostician, strategist
- 자가치유: validate 실패 → diagnose → apply_fix or strategize → retry (최대 budget/iteration 제한)
- LLM purpose 값: supervisor, code_generation, code_review, diagnose, strategize, fix
- 120개 테스트 통과 (unit 116 + integration 4)

---

### [2026-03-12] Agent-G -> ALL
**Type**: EXPORT
**Subject**: Generate Engine 완료
**Content**:
- 생성된 파일: generate/states.py, generate/engine.py, generate/nodes/(decompose,assign,gen_all,validate).py, generate/templates/(11 Jinja2), generate/__init__.py
- import 경로:
  `from architect.generate import GenerateEngine`
- 초기화: `engine = GenerateEngine(llm_router)`
- 실행: `files = await engine.generate(plan_document, decisions, output_path)`
  - `plan_document`: str — Plan 문서 Markdown
  - `decisions`: list[dict] — 사용자 결정 목록 (topic, chosen, label, rationale)
  - `output_path`: str — 출력 디렉토리 (`.vibe/` 하위에 파일 생성)
  - Returns: `dict[str, str]` — 11 filename→content 매핑
- 생성되는 11개 파일: agent.md, persona.md, plan.md, spec.md, checklist.md, interfaces.md, conventions.md, shared-memory.md, knowledge.md, errors.md, OPERATION-GUIDE.md
- 파이프라인: decompose_modules → assign_agents → generate_all_files → validate_coherence → (errors? retry max 2) → END
- LLM 호출: `purpose="generate_md"` 사용
- 동시성: asyncio.Semaphore(5)로 LLM 호출 제한
- 검증: 5개 cross-ref 체크 (plan↔checklist, agent↔persona, interfaces↔spec, prompts↔forbidden, checklist agents)
- 19개 단위 테스트 통과

---

### [2026-03-12] Agent-P -> ALL
**Type**: EXPORT
**Subject**: Plan Engine 완료
**Content**:
- 생성된 파일: plan/states.py, plan/engine.py, plan/nodes/(analyze,choices,refine,finalize).py, plan/prompts/(analyst,choice_generator,architect).py
- import 경로:
  `from architect.plan import PlanEngine, DECISION_TOPICS`
- 초기화: `engine = PlanEngine(llm_router)`
- 최초 실행: `state = await engine.start("사용자 요구사항")`
- 사용자 응답: `state = await engine.respond(state, "A")`  (선택지 ID 또는 자유 텍스트)
- 승인: `state = await engine.respond(state, "approve")`
- 완료 확인: `engine.is_complete(state)` → True
- 입력 대기 확인: `engine.needs_user_input(state)` → True (waiting_choice 또는 wait_approval)
- 현재 선택지: `engine.get_current_choices(state)` → list[Choice] | None
- Plan 문서: `engine.get_plan_document(state)` → Markdown str
- 플로우: analyze_request → present_choices → (user) → refine_spec → [loop] → generate_plan → (user approve) → END
- DECISION_TOPICS: ["tech_stack", "architecture", "features_priority", "deployment", "authentication", "database", "testing_strategy", "monitoring"]
- 19개 단위 테스트 통과

---

### [2026-03-12] Agent-L -> ALL
**Type**: EXPORT
**Subject**: LLM Router 완료
**Content**:
- 생성된 파일: llm/router.py, llm/models.py, llm/cost_tracker.py, llm/__init__.py
- import 경로:
  `from architect.llm import LLMRouter, CostTracker`
- 초기화: `router = LLMRouter(settings)`
- 텍스트 호출: `result = await router.complete(messages=[{"role":"user","content":"..."}], purpose="plan_analysis")`
- 구조화 호출: `obj = await router.complete_structured(messages, response_model=DomainAnalysis, purpose="plan_analysis")`
- 사용 가능한 purpose 값: plan_analysis, plan_choices, generate_md, code_generation, code_review, fix, diagnose, supervisor, strategize
- 비용 확인: `cost = await router.cost_tracker.get_total_cost()`
- 예산 체크: `router.cost_tracker.check_budget(max_cost_usd)` → True=예산 내
- 폴백 체인: claude-sonnet-4 → gpt-4o → deepseek-chat / claude-haiku-4.5 → gpt-4o-mini
- 재시도: 최대 3회, exponential backoff (1s, 2s, 4s)
- 예산 초과 시: LLMBudgetExceededError 자동 발생
- 16개 단위 테스트 통과

---

### [2026-03-12] Agent-A -> ALL
**Type**: EXPORT
**Subject**: Core 모듈 완료
**Content**:
- 생성된 파일: core/models.py, core/exceptions.py, core/logging.py, config.py, main.py
- import 경로:
  `from architect.core.models import PlanState, ExecuteStateV2, AgentCodeOutput, Choice, Decision, DomainAnalysis, ModuleDefinition, AgentAssignment, CodeFile, TestFile, SharedMemoryUpdate, ChecklistUpdate, ValidationResult, ReviewResult, DiagnosisResult, FixStrategy, KnowledgeEntry, GenerateState`
  `from architect.core.exceptions import ArchitectBaseError, LLMError, LLMRateLimitError, LLMResponseParseError, LLMBudgetExceededError, PlanError, GenerateError, ExecuteError, UIError, ValidationError, DispatchError, FixError, WorkspaceError`
  `from architect.core.logging import get_logger`
  `from architect.config import Settings, get_settings`
- PlanState, GenerateState, ExecuteStateV2는 TypedDict (langgraph State용)
- AgentCodeOutput은 Pydantic BaseModel (LLM Structured Output용)
- ReviewResult.passed는 model_validator로 자동 계산 (overall_score >= 3.5 AND critical_issues == 0)
- Settings는 env_prefix="ARCHITECT_" 사용, SecretStr로 API 키 보호
- CLI: `python -m architect plan|run|status|serve` (skeleton)
- 32개 단위 테스트 통과

---

### [2026-03-12] SYSTEM -> ALL
**Type**: INFO
**Subject**: 프로젝트 초기화
**Content**:
ARCHITECT v2 빌드 시작.
Phase 1: Agent-A(core) + Agent-L(llm) 병렬 작업.
Agent-A가 core/models.py 완성 후 EXPORT 남기면 Phase 2 시작 가능.
---

---

## Export Registry

```
[Agent-A] core/models.py   -> PlanState, GenerateState, ExecuteStateV2, AgentCodeOutput, Choice, Decision, ...
[Agent-A] core/exceptions.py -> ArchitectBaseError, LLMError, PlanError, ExecuteError, ...
[Agent-A] core/logging.py  -> get_logger(name)
[Agent-A] config.py        -> Settings, get_settings()
[Agent-A] main.py          -> app (typer CLI)
[Agent-L] llm/router.py    -> LLMRouter(config)
[Agent-L] llm/cost_tracker.py -> CostTracker()
[Agent-L] llm/models.py    -> PURPOSE_MODEL_MAP, FALLBACK_CHAINS, MODEL_PRICES, ModelConfig
[Agent-G] generate/engine.py -> GenerateEngine(llm_router)
[Agent-G] generate/states.py -> GenerateState (re-export)
[Agent-G] generate/nodes/   -> decompose_modules, assign_agents, generate_all_files, validate_coherence
[Agent-P] plan/engine.py   -> PlanEngine(llm_router)
[Agent-P] plan/states.py   -> DECISION_TOPICS, ChoiceList, create_initial_state, determine_next_topic
[Agent-E] execute/engine.py -> ExecuteEngine(llm_router, workspace_path)
[Agent-E] execute/supervisor/ -> plan_sprint, assign_tasks, review_code, diagnose, strategize
[Agent-E] execute/dispatcher.py -> dispatch, dispatch_parallel
[Agent-E] execute/validator.py -> validate, all_passed
[Agent-E] execute/fixer.py -> apply_fix
[Agent-E] execute/workspace.py -> Workspace
[Agent-E] execute/knowledge.py -> KnowledgeManager
[Agent-E] execute/prompts/ -> build_agent_system_prompt, build_agent_user_prompt, build_fix_prompt
```

## Dependency Tracking

| Waiting | Needs | From | Checklist | Status |
|---------|-------|------|-----------|--------|
| Agent-P | LLMRouter | Agent-L | #7 | [DONE] |
| Agent-P | core/models.py | Agent-A | #2 | [DONE] |
| Agent-G | LLMRouter | Agent-L | #7 | [DONE] |
| Agent-G | core/models.py | Agent-A | #2 | [DONE] |
| Agent-E | Plan+Generate 완료 | Agent-P,G | P2 전체 | [DONE] |
| Agent-U | Execute Engine | Agent-E | #48 | [DONE] |

## Decision Log

| Date | Decision | Rationale | Scope |
|------|----------|-----------|-------|
| 2026-03-12 | LangGraph for all engines | 일관된 StateGraph 패턴 | ALL |
| 2026-03-12 | Supervisor 5-role 분리 | 실제 PM 프로세스 모사 | Agent-E |
| 2026-03-12 | xterm.js for terminal | 성숙한 WebSocket 터미널 | Agent-U |
| 2026-03-12 | react-diff-viewer for diff | unified diff 표준 지원 | Agent-U |
