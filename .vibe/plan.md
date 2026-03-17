# plan.md — ARCHITECT Implementation Plan

> Version: 2.0.0

---

## Phase 1: Foundation (Agent-A + Agent-L 병렬)

### P1-1. Core Models & Config [Agent-A]
- [ ] pyproject.toml (전체 의존성: langgraph, litellm, fastapi, pydantic 등)
- [ ] src/architect/__init__.py
- [ ] src/architect/core/models.py (PlanState, GenerateState, ExecuteStateV2, AgentCodeOutput, CodeFile, Choice, Decision, DomainAnalysis, ModuleDefinition, AgentAssignment, ValidationResult, FixStrategy, KnowledgeEntry, SharedMemoryUpdate, ChecklistUpdate)
- [ ] src/architect/core/exceptions.py (ArchitectBaseError + 하위 예외 계층)
- [ ] src/architect/core/logging.py (structlog 설정)
- [ ] src/architect/config.py (Pydantic Settings: LLM keys, budget, limits, paths)
- [ ] src/architect/main.py (typer CLI: plan, run, status, serve 명령)

### P1-2. LLM Router [Agent-L]
- [ ] src/architect/llm/__init__.py (LLMRouter, CostTracker export)
- [ ] src/architect/llm/router.py (complete, complete_structured, 폴백 체인, 비동기)
- [ ] src/architect/llm/models.py (PURPOSE_MODEL_MAP, FALLBACK_CHAINS)
- [ ] src/architect/llm/cost_tracker.py (토큰/비용 추적, budget check)

---

## Phase 2: Engines + UI 기반 (Agent-P, Agent-G, Agent-U 병렬)

### P2-1. Plan Engine [Agent-P]
- [ ] src/architect/plan/states.py (PlanState TypedDict)
- [ ] src/architect/plan/nodes/analyze.py (요구사항 분석 -> DomainAnalysis)
- [ ] src/architect/plan/nodes/choices.py (선택지 생성 -> list[Choice])
- [ ] src/architect/plan/nodes/refine.py (사용자 응답 처리 -> Decision)
- [ ] src/architect/plan/nodes/finalize.py (Plan 문서 Markdown 생성)
- [ ] src/architect/plan/prompts/ (analyst.py, architect.py, choice_generator.py)
- [ ] src/architect/plan/engine.py (StateGraph 조립 + interrupt_before)
- [ ] tests/unit/plan/ (Plan Engine 단위 테스트)

### P2-2. Generate Engine [Agent-G]
- [ ] src/architect/generate/states.py (GenerateState TypedDict)
- [ ] src/architect/generate/nodes/decompose.py (Plan -> 독립 모듈 분해)
- [ ] src/architect/generate/nodes/assign.py (모듈 -> Agent 할당 + 병렬 분석)
- [ ] src/architect/generate/nodes/gen_agent_md.py
- [ ] src/architect/generate/nodes/gen_persona.py
- [ ] src/architect/generate/nodes/gen_plan_md.py
- [ ] src/architect/generate/nodes/gen_spec.py (가장 중요 - 코드 레벨 사양)
- [ ] src/architect/generate/nodes/gen_checklist.py
- [ ] src/architect/generate/nodes/gen_interfaces.py
- [ ] src/architect/generate/nodes/gen_conventions.py
- [ ] src/architect/generate/nodes/gen_shared_memory.py
- [ ] src/architect/generate/nodes/gen_prompts.py (OPERATION-GUIDE.md)
- [ ] src/architect/generate/nodes/validate.py (파일 간 정합성 검증)
- [ ] src/architect/generate/engine.py (StateGraph 조립)
- [ ] src/architect/generate/templates/ (Jinja2 기본 템플릿 10개)
- [ ] tests/unit/generate/

### P2-3. UI Foundation [Agent-U]
- [ ] src/architect/ui/app.py (FastAPI 앱 + CORS + WebSocket)
- [ ] src/architect/ui/routes/plan.py (Plan 대화 API: POST /plan/start, /plan/respond, /plan/choices)
- [ ] src/architect/ui/routes/diff.py (GET /diff/{phase} -> unified diff)
- [ ] src/architect/ui/routes/execute.py (POST /execute/start, /execute/stop, GET /execute/status)
- [ ] src/architect/ui/routes/preview.py (GET /preview/files, /preview/tests)
- [ ] src/architect/ui/routes/terminal.py (WebSocket /ws/terminal -> pty)
- [ ] src/architect/ui/ws/progress.py (WebSocket /ws/progress -> 실시간 스트림)
- [ ] frontend/ 초기화 (React + TypeScript + Tailwind + Vite)
- [ ] frontend/src/pages/PlanPage.tsx (채팅 + 선택지 카드)
- [ ] frontend/src/pages/DiffPage.tsx (react-diff-viewer)
- [ ] frontend/src/pages/ExecutePage.tsx (진행률 + Start/Stop)
- [ ] frontend/src/pages/PreviewPage.tsx (파일 트리 + 코드 뷰어)
- [ ] frontend/src/pages/TerminalPage.tsx (xterm.js)
- [ ] frontend/src/components/ (ChatMessage, ChoiceSelector, DiffViewer, FileTree, TerminalEmulator, ProgressTracker)

---

## Phase 3: Execute Engine (Agent-E 집중 + Agent-U 완성)

### P3-1. Execute Engine Core [Agent-E]
- [ ] src/architect/execute/states.py (ExecuteStateV2 TypedDict)
- [ ] src/architect/execute/supervisor/planner.py (스프린트 계획 + 리스크 평가)
- [ ] src/architect/execute/supervisor/assigner.py (Agent 할당 + 지식 주입)
- [ ] src/architect/execute/supervisor/reviewer.py (코드 리뷰 6차원)
- [ ] src/architect/execute/supervisor/diagnostician.py (에러 근본원인 진단)
- [ ] src/architect/execute/supervisor/strategist.py (7가지 전략 결정)
- [ ] src/architect/execute/dispatcher.py (프롬프트 조립 + LLM 병렬 호출)
- [ ] src/architect/execute/validator.py (syntax, lint, typecheck, unit_test, integration)
- [ ] src/architect/execute/fixer.py (Fix 전략 적용)
- [ ] src/architect/execute/workspace.py (파일 I/O + Git 자동 커밋)
- [ ] src/architect/execute/knowledge.py (지식 축적/검색/활용)
- [ ] src/architect/execute/prompts/ (agent_system.py, agent_user.py, fix_prompt.py)
- [ ] src/architect/execute/engine.py (Supervisor Loop StateGraph 전체 조립)
- [ ] tests/unit/execute/
- [ ] tests/integration/ (간단한 TODO API 프로젝트로 E2E)

### P3-2. UI Execute Integration [Agent-U]
- [ ] Execute 진행률 WebSocket 연동
- [ ] Diff 뷰에 실시간 파일 변경 반영
- [ ] Terminal WebSocket <-> pty 연결
- [ ] Preview에 테스트 결과 실시간 표시

---

## Phase 4: Integration + Hardening

### P4-1. Full Pipeline [Agent-A + Agent-E]
- [ ] main.py에서 Plan -> Generate -> Execute -> Deliver 전체 연결
- [ ] `architect serve`로 웹 UI 시작 -> Plan -> Start -> 자율 실행 -> 결과 Diff
- [ ] CLI 전체 플로우 테스트
- [ ] E2E 테스트 (간단한 TODO REST API 프로젝트 자동 생성)

### P4-2. Validation [전체]
- [ ] 실제 프로젝트 3종 검증 (CRUD API, CLI 도구, LangGraph 에이전트)
- [ ] 에러 패턴 분석 및 Fix 전략 보강
- [ ] Retrospective 시스템 실전 검증
- [ ] 비용 최적화 (모델 선택, 프롬프트 축소)
- [ ] README + 사용법 문서

---

## Priority Matrix

| Feature | Importance | Urgency | Phase | Agent |
|---------|-----------|---------|-------|-------|
| Core Models | 5/5 | 5/5 | P1 | A |
| LLM Router | 5/5 | 5/5 | P1 | L |
| Plan Engine | 5/5 | 4/5 | P2 | P |
| Generate Engine | 5/5 | 4/5 | P2 | G |
| UI Foundation | 4/5 | 3/5 | P2 | U |
| Supervisor 5-Role | 5/5 | 5/5 | P3 | E |
| Dispatcher | 5/5 | 5/5 | P3 | E |
| Validator + Fixer | 5/5 | 4/5 | P3 | E |
| Knowledge System | 4/5 | 3/5 | P3 | E |
| Diff View | 4/5 | 3/5 | P2 | U |
| Terminal | 3/5 | 2/5 | P3 | U |
| Retrospective | 4/5 | 3/5 | P3 | E |
| E2E Test | 5/5 | 4/5 | P4 | ALL |
