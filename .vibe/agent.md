# agent.md — ARCHITECT Master Orchestration

> Version: 2.0.0 | Last Updated: 2026-03-12

---

## 1. Boot Sequence

```
(1) agent.md        <- 구조, 역할, 규칙
(2) checklist.md    <- 현재 진행 상태
(3) persona.md      <- 자신의 역할 로드
(4) plan.md         <- 구현 대상
(5) spec.md         <- 기술 사양
(6) shared-memory.md <- 타 Agent 메시지
(7) interfaces.md   <- 모듈 계약
(8) conventions.md  <- 코딩 규칙
(9) knowledge.md    <- 축적된 해결 지식
(10) errors.md      <- 에러 이력
[작업 시작]
[완료 후] checklist + shared-memory + knowledge 업데이트
```

---

## 2. System Overview

ARCHITECT는 사용자와 Plan Mode 대화로 기술 명세를 확정한 뒤, 자율적으로 다수의 코딩 에이전트를 운용하여 실제 동작하는 코드를 생성하는 시스템이다.

```
PLAN MODE (사용자 대화)
  -> GENERATE MODE (MD 파일 자동 생성)
    -> EXECUTE MODE (자율 Supervisor Loop)
      -> DELIVER MODE (Diff 확인 + Preview)
```

UI 구성:
- Plan Mode: 멀티턴 대화 + 선택지 UI
- Diff View: 생성/변경 코드를 diff 형태로 확인
- Start Button: 사용자 승인 후 자율 실행 시작
- Preview: 실행 결과 미리보기 (테스트 결과, 파일 트리)
- Terminal: 직접 명령어 입력 가능

---

## 3. Project Directory Structure

```
architect/
+-- src/architect/
|   +-- __init__.py
|   +-- main.py                           # [Agent-A] CLI 엔트리포인트
|   +-- config.py                         # [Agent-A] Pydantic Settings
|   +-- core/                             # [Agent-A] 공유 모델, 예외, 로깅
|   |   +-- models.py                     #   PlanState, ExecuteState, AgentCodeOutput...
|   |   +-- exceptions.py
|   |   +-- logging.py
|   +-- plan/                             # [Agent-P] Plan Engine
|   |   +-- engine.py                     #   LangGraph StateGraph
|   |   +-- states.py                     #   PlanState TypedDict
|   |   +-- nodes/                        #   analyze, choices, refine, finalize
|   |   +-- prompts/
|   +-- generate/                         # [Agent-G] Generate Engine
|   |   +-- engine.py                     #   LangGraph StateGraph
|   |   +-- states.py
|   |   +-- nodes/                        #   decompose, assign, gen_*.py, validate
|   |   +-- templates/                    #   Jinja2 .md.j2 템플릿
|   +-- execute/                          # [Agent-E] Execute Engine (Supervisor)
|   |   +-- engine.py                     #   Supervisor Loop StateGraph
|   |   +-- states.py                     #   ExecuteStateV2
|   |   +-- supervisor/                   #   PM 5역할
|   |   |   +-- planner.py               #   스프린트 계획
|   |   |   +-- assigner.py              #   Agent 할당 + 지식 주입
|   |   |   +-- reviewer.py              #   코드 리뷰 (6차원)
|   |   |   +-- diagnostician.py         #   에러 근본원인 진단
|   |   |   +-- strategist.py            #   전략 결정 (7가지)
|   |   +-- dispatcher.py                #   Agent LLM 호출 + 프롬프트 조립
|   |   +-- validator.py                 #   lint, test, import 검증
|   |   +-- fixer.py                     #   Fix Agent 디스패치
|   |   +-- workspace.py                 #   파일시스템 + Git
|   |   +-- knowledge.py                 #   지식 축적/검색
|   |   +-- prompts/
|   +-- llm/                             # [Agent-L] LLM 라우팅
|   |   +-- router.py
|   |   +-- models.py
|   |   +-- cost_tracker.py
|   +-- ui/                              # [Agent-U] 웹 UI
|       +-- app.py                       #   FastAPI + WebSocket
|       +-- static/                      #   프론트엔드 에셋
|       +-- templates/                   #   HTML 템플릿
|       +-- routes/
|       |   +-- plan.py                  #   Plan Mode 대화 API
|       |   +-- execute.py               #   실행 제어 API
|       |   +-- diff.py                  #   Diff 조회 API
|       |   +-- terminal.py              #   Terminal WebSocket
|       |   +-- preview.py               #   Preview API
|       +-- ws/
|           +-- progress.py              #   실시간 진행률
|           +-- terminal.py              #   Terminal 양방향
+-- frontend/                            # [Agent-U] React 프론트엔드
|   +-- src/
|   |   +-- App.tsx
|   |   +-- pages/
|   |   |   +-- PlanPage.tsx             #   대화 + 선택지 UI
|   |   |   +-- DiffPage.tsx             #   Diff 뷰어
|   |   |   +-- ExecutePage.tsx          #   진행률 + Start 버튼
|   |   |   +-- PreviewPage.tsx          #   결과 미리보기
|   |   |   +-- TerminalPage.tsx         #   xterm.js 터미널
|   |   +-- components/
|   |       +-- ChatMessage.tsx
|   |       +-- ChoiceSelector.tsx
|   |       +-- DiffViewer.tsx           #   react-diff-viewer
|   |       +-- FileTree.tsx
|   |       +-- TerminalEmulator.tsx     #   xterm.js 래퍼
|   |       +-- ProgressTracker.tsx
|   +-- package.json
+-- tests/
+-- pyproject.toml
```

---

## 4. Agent-Directory Ownership

| Agent | Role | Directories | Phase |
|-------|------|-------------|-------|
| Agent-A | Core Architect | core/, config.py, main.py | P1 |
| Agent-L | LLM Specialist | llm/ | P1 |
| Agent-P | Plan Engineer | plan/ | P2 |
| Agent-G | Generate Engineer | generate/, templates/ | P2 |
| Agent-E | Execute Engineer | execute/ | P3 |
| Agent-U | UI Engineer | ui/, frontend/ | P2-P3 |

---

## 5. Coordination Rules

```
[RULE-1] 자기 디렉토리만 생성/수정. 위반 시 Reviewer가 차단.
[RULE-2] core/는 Agent-A 관리, 전원 import 가능.
[RULE-3] interfaces.md 변경 시 shared-memory.md ALERT 필수.
[RULE-4] 완료 시: checklist + shared-memory + knowledge 반드시 업데이트.
[RULE-5] 다른 Agent 코드 수정 필요 시 shared-memory.md에 REQUEST.
```

## 6. Parallel Matrix

```
          A    P    G    E    L    U
Agent-A   -   [OK] [OK] [OK] [OK] [OK]
Agent-P  [OK]  -  [DEP] [DEP] [DEP] [OK]
Agent-G  [OK] [DEP]  -  [DEP] [OK] [OK]
Agent-E  [OK] [DEP] [DEP]  -  [DEP] [DEP]
Agent-L  [OK] [DEP] [OK] [DEP]  -  [OK]
Agent-U  [OK] [OK] [OK] [DEP] [OK]  -
```

## 7. Critical Path

```
Phase 1 (병렬): Agent-A (core) + Agent-L (llm)
Phase 2 (병렬): Agent-P (plan) + Agent-G (generate) + Agent-U (UI 기반)
Phase 3 (집중): Agent-E (execute) + Agent-U (UI 완성)
Phase 4 (통합): 전체 연결 + E2E 테스트
```
