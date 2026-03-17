# ARCHITECT — Autonomous Multi-Agent Coding Orchestration System

## Technical Specification Document

> Version: 1.0.0
> Date: 2026-03-11
> Codename: ARCHITECT
> Subtitle: Plan Once, Build Autonomously

---

# Part 1. System Overview

## 1.1 What This System Does

ARCHITECT는 사용자가 "어떤 프로그램을 만들고 싶다"고 말하면, 대화를 통해 기술 명세를 정교하게 만들고, 명세가 확정되면 이후 완전 자율적으로 다수의 코딩 에이전트를 운용하여 실제 동작하는 프로덕션 코드를 생성하는 시스템이다.

핵심 원칙: 사용자는 Plan Mode에서만 개입한다. 실행(Execute Mode)부터는 시스템이 스스로 판단하고, 구현하고, 테스트하고, 검증하고, 실패하면 자동 수정한다.

```
[사용자]
   |
   | "이런 프로그램 만들어줘"
   v
+---------------------------+
|       PLAN MODE           |  <-- 사용자 개입 구간 (유일)
|  멀티턴 대화              |
|  선택지 제시 + 확정       |
|  기술 명세서 자동 생성    |
+---------------------------+
   |
   | [사용자: "실행해"]
   v
+---------------------------+
|     GENERATE MODE         |  <-- 자동
|  8+ MD 오케스트레이션     |
|  파일 자동 생성           |
+---------------------------+
   |
   v
+---------------------------+
|     EXECUTE MODE          |  <-- 완전 자율
|  Agent 다중 디스패치      |
|  코드 구현                |
|  테스트 실행              |
|  검증 + 자동 수정         |
|  반복 (통과할 때까지)     |
+---------------------------+
   |
   v
+---------------------------+
|     DELIVER MODE          |
|  최종 코드 + 보고서       |
|  사용자에게 전달          |
+---------------------------+
```

## 1.2 System Modes

| Mode | 사용자 개입 | 설명 |
|------|-----------|------|
| PLAN | 필수 (대화) | 멀티턴 대화로 요구사항 정제, 기술 선택, 아키텍처 확정 |
| GENERATE | 없음 (자동) | Plan 결과를 8+ MD 오케스트레이션 파일로 변환 |
| EXECUTE | 없음 (자동) | Agent 디스패치, 코드 구현, 테스트, 검증의 자율 루프 |
| DELIVER | 알림만 | 완성된 코드와 보고서를 사용자에게 전달 |

## 1.3 Why Not Mockup

기존 AI 코딩 도구의 문제:
- 단일 세션에서 전체 코드를 생성하려다 컨텍스트 초과
- Mockup/Placeholder 코드를 생성하고 "나머지는 구현하세요"로 끝남
- 모듈 간 인터페이스 불일치
- 테스트 없이 코드만 출력

ARCHITECT의 해결 방식:
- 여러 Agent가 각자 담당 모듈만 구현 (컨텍스트 효율)
- interfaces.md로 모듈 간 계약 강제 (불일치 방지)
- 모든 Agent가 실제 실행 가능한 코드 + 테스트를 작성
- Supervisor가 테스트 실행 결과를 검증하고 실패 시 재지시

---

# Part 2. Architecture

## 2.1 High-Level Architecture

```
+================================================================+
|                    ARCHITECT SYSTEM                              |
|                                                                  |
|  +------------------+     +------------------+                   |
|  |   Plan Engine    |     |  Generate Engine |                   |
|  |  (LangGraph)     |---->|  (LangGraph)     |                   |
|  |                  |     |                  |                   |
|  |  - Analyst Agent |     |  - DocGen Agent  |                   |
|  |  - Architect     |     |  - SchemaGen     |                   |
|  |    Agent         |     |    Agent         |                   |
|  +------------------+     +--------+---------+                   |
|                                    |                             |
|                           8+ MD Files                            |
|                                    |                             |
|                           +--------v---------+                   |
|                           |  Execute Engine  |                   |
|                           |  (LangGraph)     |                   |
|                           |                  |                   |
|                           |  - Supervisor    |                   |
|                           |  - Dispatcher    |                   |
|                           |  - Validator     |                   |
|                           |  - Fixer         |                   |
|                           +--------+---------+                   |
|                                    |                             |
|                    +-------+-------+-------+-------+             |
|                    |       |       |       |       |             |
|                    v       v       v       v       v             |
|                 Agent-A Agent-B Agent-C Agent-D Agent-E          |
|                 (Code)  (Code)  (Code)  (Code)  (Code)          |
|                    |       |       |       |       |             |
|                    v       v       v       v       v             |
|                +----------------------------------------+        |
|                |          Shared Workspace              |        |
|                |  (Git Repo + .vibe/ MD Files)          |        |
|                +----------------------------------------+        |
|                                    |                             |
|                           +--------v---------+                   |
|                           |  Deliver Engine  |                   |
|                           +------------------+                   |
+================================================================+
```

## 2.2 Component Breakdown

### 2.2.1 Plan Engine

사용자와 대화하여 기술 명세를 만드는 엔진.

```
Plan Engine (LangGraph StateGraph)

States:
  - requirements_raw: str        # 사용자 초기 입력
  - clarifications: list[dict]   # Q&A 이력
  - tech_decisions: dict         # 기술 선택 결과
  - architecture: dict           # 아키텍처 확정
  - plan_document: str           # 최종 Plan 문서
  - user_approved: bool          # 사용자 승인 여부

Nodes:
  analyze_request    → 요구사항 분석, 질문 생성
  present_choices    → 선택지 제시 (기술 스택, 아키텍처 패턴 등)
  refine_spec        → 사용자 응답 기반 명세 정제
  generate_plan      → 최종 Plan 문서 생성
  user_approval      → 사용자 승인 대기 (Human-in-the-loop)

Edges:
  analyze_request → present_choices
  present_choices → (사용자 응답 대기) → refine_spec
  refine_spec → (충분한가?) → generate_plan 또는 present_choices (반복)
  generate_plan → user_approval
  user_approval → (승인) → END 또는 (수정) → refine_spec
```

### 2.2.2 Generate Engine

Plan 문서를 8+ MD 오케스트레이션 파일로 변환하는 엔진.

```
Generate Engine (LangGraph StateGraph)

States:
  - plan_document: str
  - project_structure: dict      # 디렉토리 트리
  - agent_assignments: dict      # Agent별 담당 모듈
  - generated_files: dict[str, str]  # filename → content

Nodes:
  decompose_modules  → Plan을 독립 모듈로 분해
  assign_agents      → 모듈별 Agent 할당 (병렬 가능성 분석)
  generate_agent_md  → agent.md 생성
  generate_persona   → persona.md 생성 (Agent별 Instructions/Knowledge/Tools)
  generate_plan_md   → plan.md 생성
  generate_spec_md   → spec.md 생성 (코드 레벨 사양)
  generate_checklist → checklist.md 생성
  generate_interfaces → interfaces.md 생성 (모듈 간 계약)
  generate_conventions → conventions.md 생성
  generate_shared_memory → shared-memory.md 초기화
  generate_prompts   → OPERATION-GUIDE.md (각 Agent 프롬프트)
  validate_coherence → 파일 간 정합성 검증

Edges:
  decompose_modules → assign_agents → (병렬)
  [generate_agent_md, generate_persona, generate_plan_md,
   generate_spec_md, generate_interfaces, generate_conventions]
  → generate_checklist → generate_shared_memory
  → generate_prompts → validate_coherence → END
```

### 2.2.3 Execute Engine (핵심)

자율적으로 Agent를 디스패치하고, 코드를 구현하고, 검증하는 엔진.

```
Execute Engine (LangGraph StateGraph)

States:
  - vibe_files: dict[str, str]     # .vibe/ MD 파일 내용
  - current_phase: int              # 현재 Phase (1~4)
  - active_agents: list[str]        # 현재 활성 Agent ID
  - agent_results: dict[str, dict]  # Agent별 작업 결과
  - test_results: dict              # 테스트 실행 결과
  - iteration: int                  # 현재 반복 횟수
  - max_iterations: int             # 최대 반복 (안전장치)
  - workspace_path: str             # Git 레포 경로
  - status: str                     # running | completed | failed

Nodes:
  read_state          → .vibe/ 파일에서 현재 상태 로드
  select_phase        → checklist 기반 다음 Phase 결정
  plan_dispatch       → 이번 Phase에서 어떤 Agent를 투입할지 결정
  dispatch_agents     → Agent별 프롬프트 생성 + LLM API 병렬 호출
  collect_results     → Agent 응답(코드) 수집
  write_to_workspace  → 코드를 파일시스템에 쓰기
  run_lint            → ruff, mypy 실행
  run_tests           → pytest 실행
  evaluate_results    → 테스트 결과 분석
  fix_issues          → 실패한 부분 수정 Agent 디스패치
  update_vibe_files   → checklist, shared-memory 등 업데이트
  phase_complete      → Phase 완료 판단 → 다음 Phase 또는 END

Edges:
  read_state → select_phase → plan_dispatch → dispatch_agents
  dispatch_agents → collect_results → write_to_workspace
  write_to_workspace → run_lint → run_tests → evaluate_results
  evaluate_results → (통과) → update_vibe_files → phase_complete
  evaluate_results → (실패) → fix_issues → write_to_workspace (루프)
  phase_complete → (다음 Phase 있음) → select_phase (루프)
  phase_complete → (전체 완료) → END

  fix_issues 루프 안전장치:
    iteration >= max_iterations → 강제 종료 + 실패 보고
```

### 2.2.4 Coding Agent (LLM 호출 단위)

각 Coding Agent는 독립된 LLM 호출이다. 시스템 프롬프트에 persona를 주입하고, 유저 프롬프트에 구체적 작업 지시를 넣는다.

```
Single Agent Call:

system_prompt = persona.md의 해당 Agent 섹션
                + conventions.md 전문
                + interfaces.md의 관련 섹션

user_prompt   = "이번 작업 지시"
                + spec.md의 관련 섹션
                + shared-memory.md에서 필요한 EXPORT 정보
                + 기존 코드 파일 (수정이 필요한 경우)

response      = 생성된 코드 파일들 (JSON 구조화 출력)
```

## 2.3 Data Flow

```
[사용자 입력]
     |
     v
Plan Engine ──── plan_document (기술 명세 텍스트)
     |
     v
Generate Engine ── .vibe/ 8+ MD 파일
     |               + 프로젝트 디렉토리 구조
     v
Execute Engine
     |
     +── [Phase 1] Agent-A,B,D,F 병렬 디스패치
     |       |
     |       +── Agent 응답: {파일명: 코드내용, ...}
     |       |
     |       +── 파일 시스템에 쓰기
     |       |
     |       +── lint + test 실행
     |       |
     |       +── (실패 시) Fix Agent 재디스패치
     |       |
     |       +── checklist.md, shared-memory.md 자동 업데이트
     |
     +── [Phase 2] Agent-C,D,E 디스패치
     |       |
     |       +── (같은 루프)
     |
     +── [Phase 3~4] ...
     |
     v
Deliver Engine ── 최종 코드 + 실행 보고서
```

---

# Part 3. Plan Engine — Detailed Design

## 3.1 Plan Mode Conversation Flow

```
사용자: "기업 데이터를 온톨로지화하는 API를 만들고 싶어"
     |
     v
[Analyst Agent]
  분석: 요구사항 키워드 추출
  - 도메인: Enterprise Data, Ontology, Knowledge Graph
  - 유형: API Platform (Backend)
  - 핵심 기능: 문서 파싱, 온톨로지 구축, KG 관리, 증분 업데이트
     |
     v
[선택지 1: 기술 스택]
  "다음 중 원하는 기술 스택을 선택하세요:"
  A) Python + FastAPI + Neo4j + LangGraph (권장)
  B) TypeScript + NestJS + Neptune + Custom
  C) Go + Gin + Dgraph
  D) 직접 지정

사용자: "A"
     |
     v
[선택지 2: 아키텍처 패턴]
  "아키텍처 패턴을 선택하세요:"
  A) Monolithic API (빠른 개발, 소규모)
  B) Microservices + Event-Driven (확장성, 중규모+)
  C) Serverless + Managed Services (운영 최소화)

사용자: "B"
     |
     v
[선택지 3: 핵심 기능 우선순위]
  "우선순위를 정해주세요 (드래그 정렬):"
  1. 문서 파싱 (PDF, Word, Excel, DB)
  2. LLM 기반 엔티티 추출
  3. 증분 업데이트
  4. GraphRAG 검색
  5. CI/CD 통합
  6. 멀티테넌트

사용자: [순서 정렬]
     |
     v
[선택지 4~N: 세부 결정들...]
  - LLM 모델 선택 (Claude / GPT / 로컬)
  - 배포 환경 (GKE / EKS / Docker Compose)
  - 인증 방식 (JWT / OAuth / API Key)
  - ...
     |
     v
[Plan 문서 생성]
  "기술 명세서가 완성되었습니다. 검토해주세요."
  [Plan 문서 전문 표시]

사용자: "승인" 또는 "이 부분 수정해줘: ..."
     |
     v
[승인됨] → Generate Mode로 전환
```

## 3.2 Plan Engine State

```python
class PlanState(TypedDict):
    # 입력
    user_request: str                    # 최초 요구사항
    conversation_history: list[dict]     # 멀티턴 대화 이력

    # 분석 결과
    domain_analysis: dict                # 도메인 분석
    feature_list: list[dict]             # 기능 목록 + 우선순위
    tech_stack: dict                     # 확정된 기술 스택
    architecture_pattern: str            # 아키텍처 패턴

    # 세부 결정
    decisions: list[dict]                # 모든 선택지 + 사용자 결정
    open_questions: list[str]            # 아직 미결정 항목

    # 출력
    plan_document: str                   # 최종 Plan 문서 (Markdown)
    approved: bool                       # 사용자 승인 여부
```

## 3.3 선택지 생성 전략

각 선택지는 LLM이 다음 기준으로 생성한다:

```
선택지 생성 프롬프트:

You are a senior software architect.

Given the following requirements and decisions made so far:
{context}

Generate 2-4 concrete choices for: {decision_topic}

For each choice, provide:
1. Label: 짧은 이름 (2-4단어)
2. Description: 한 줄 설명
3. Pros: 장점 2-3개
4. Cons: 단점 1-2개
5. Recommended: 이 프로젝트에 권장하는지 여부 + 이유

Format: JSON array
```

선택지 카테고리 목록 (Plan Engine이 순차적으로 진행):

```
필수 결정 (반드시 확인):
  1. 기술 스택 (언어, 프레임워크, DB)
  2. 아키텍처 패턴
  3. 핵심 기능 목록 + 우선순위
  4. 배포 환경
  5. 인증/보안 방식

조건부 결정 (선택에 따라 추가):
  6. LLM 모델 + 폴백 전략 (LLM 사용 시)
  7. 메시지 큐 선택 (이벤트 기반 시)
  8. DB 스키마 설계 방식 (DB 사용 시)
  9. CI/CD 파이프라인 (배포 필요 시)
  10. 모니터링 스택 (프로덕션 레벨 시)
```

---

# Part 4. Generate Engine — Detailed Design

## 4.1 MD File Generation Pipeline

Plan 문서로부터 8+ MD 파일을 생성하는 과정:

```
plan_document
     |
     v
[1. Module Decomposition]
  Plan 문서를 분석하여 독립 모듈로 분해
  출력: modules = [
    {name: "api", description: "REST API 레이어", dependencies: []},
    {name: "ingestion", description: "문서 파싱", dependencies: []},
    {name: "extraction", description: "LLM 추출", dependencies: ["llm"]},
    ...
  ]
     |
     v
[2. Agent Assignment]
  모듈별 Agent 할당 + 병렬 가능성 분석
  출력: assignments = {
    "Agent-A": {modules: ["api", "auth"], phase: 1},
    "Agent-B": {modules: ["ingestion"], phase: 1},
    ...
  }
  + dependency_graph (어떤 Agent가 어떤 Agent를 기다려야 하는지)
     |
     v
[3. Parallel Generation] (6개 LLM 호출 동시)
  +--> agent.md 생성 (디렉토리 구조, Agent Map, 부팅 시퀀스)
  +--> persona.md 생성 (Agent별 Instructions/Knowledge/Tools)
  +--> plan.md 생성 (Phase별 Task 목록)
  +--> spec.md 생성 (코드 레벨 사양, 인터페이스 코드)
  +--> interfaces.md 생성 (함수 시그니처, 타입 정의)
  +--> conventions.md 생성 (코딩 규칙)
     |
     v
[4. Sequential Generation] (앞의 결과를 참조해야 함)
  checklist.md 생성 (plan.md의 Task를 테이블로 변환)
  shared-memory.md 초기화
  OPERATION-GUIDE.md 생성 (Agent별 프롬프트)
     |
     v
[5. Coherence Validation]
  생성된 파일 간 정합성 검증:
  - plan.md의 모든 Task가 checklist.md에 존재하는지
  - persona.md의 Agent가 agent.md의 Agent Map과 일치하는지
  - interfaces.md의 함수 시그니처가 spec.md와 일치하는지
  - OPERATION-GUIDE의 프롬프트가 persona.md의 금지사항을 포함하는지
  불일치 발견 시 → 해당 파일 재생성
```

## 4.2 각 MD 파일 생성 프롬프트 구조

### agent.md 생성

```
System: You are an expert software project architect.

Input:
- Plan document: {plan_document}
- Module decomposition: {modules}
- Agent assignments: {assignments}
- Dependency graph: {dependency_graph}

Generate agent.md with the following sections:
1. Boot Sequence: Agent가 세션 시작 시 읽는 파일 순서
2. Project Directory Structure: 전체 디렉토리 트리
3. Agent-Directory Ownership Map: Agent별 담당 디렉토리
4. Agent Coordination Rules: 소유권 원칙, 완료 프로토콜, 충돌 해소
5. Parallel Work Matrix: 어떤 Agent 쌍이 동시 작업 가능한지
6. Critical Path: Phase별 의존 순서
7. File Authority Matrix: 파일별 읽기/쓰기 권한

Rules:
- 디렉토리 경로는 구체적으로 (src/api/routes/ 수준)
- 이모지 사용 금지, 텍스트 마커 사용 ([DONE], [TODO] 등)
- 모든 Agent는 A부터 알파벳 순서로 명명
```

### persona.md 생성

```
System: You are an expert at defining AI agent personas for coding tasks.

Input:
- Agent assignments: {assignments}
- Tech stack decisions: {tech_stack}
- Module specifications: {module_specs}

For each Agent, generate a persona section with exactly three parts:

[INSTRUCTIONS] 지침:
- 역할 한 줄 정의
- 핵심 원칙 5-7개 (구체적, 측정 가능)
- 코딩 스타일 3-5개
- 금지 사항 3-5개 (반드시 [X] 마커 사용)
- 담당 범위 (디렉토리 경로)

[KNOWLEDGE] 지식:
- 사용하는 라이브러리의 공식 문서 URL (3-5개)
- 프로젝트 내부 참조 파일 (spec.md 섹션 번호 등)
- 관련 논문/패턴 이름 (필요 시)

[TOOLS] 도구:
- 코드 실행 환경 (Python 버전, 주요 도구)
- 테스트 실행 명령
- 린트/포맷 도구
- 웹 검색 사용 조건

Rules:
- 각 Agent의 금지 사항에는 반드시 "다른 Agent 담당 디렉토리 수정 금지" 포함
- Knowledge는 검증 가능한 URL만 포함
- 이모지 금지
```

### spec.md 생성 (가장 중요)

```
System: You are a senior software engineer writing detailed technical specifications.

Input:
- Plan document: {plan_document}
- Tech stack: {tech_stack}
- Module decomposition: {modules}
- Interfaces: {interfaces}

Generate spec.md with:
1. Technology Stack: 전체 의존성 목록 (pyproject.toml 수준)
2. Core Module Specifications: 각 모듈의 핵심 클래스/함수 코드 (Pydantic 모델, 추상 클래스)
3. Data Models: 공유 도메인 모델 전체 코드
4. Database Schema: DDL 또는 Cypher 스키마
5. API Endpoints: 전체 엔드포인트 사양
6. Pipeline/Workflow: 상태머신 정의
7. Directory-Specific Notes: 모듈별 구현 주의사항

Rules:
- 코드는 반드시 실행 가능한 수준으로 작성 (import문 포함)
- Pydantic 모델은 전체 필드 + 타입 + 기본값 포함
- 추상 클래스는 메서드 시그니처 + docstring 포함
- Mockup 코드 금지: "여기에 구현" 같은 주석 없이 실제 로직 포함
```

---

# Part 5. Execute Engine — Detailed Design

## 5.1 Supervisor Loop (핵심 자율 실행 루프)

```python
class ExecuteState(TypedDict):
    # 환경
    workspace_path: str
    vibe_files: dict[str, str]

    # 현재 상태
    current_phase: int
    phase_tasks: list[dict]           # 이번 Phase의 Task 목록
    completed_tasks: list[str]        # 완료된 Task ID
    failed_tasks: list[dict]          # 실패한 Task + 에러 정보

    # Agent 운용
    active_agents: list[dict]         # 현재 디스패치된 Agent 정보
    agent_outputs: dict[str, dict]    # Agent별 출력 (코드 파일)

    # 검증
    lint_results: dict                # ruff/mypy 결과
    test_results: dict                # pytest 결과
    integration_check: dict           # 모듈 간 import 검증

    # 루프 제어
    iteration: int
    max_iterations: int               # Phase당 최대 반복 (기본: 5)
    phase_status: str                 # planning | executing | testing | fixing | complete
```

## 5.2 Supervisor Decision Logic

```
Supervisor는 매 루프마다 다음을 판단한다:

1. 이번 Phase에서 어떤 Agent를 투입하는가?
   → agent.md의 Critical Path + checklist.md의 미완료 항목 기반
   → 병렬 가능한 Agent는 동시 디스패치

2. Agent에게 무엇을 지시하는가?
   → OPERATION-GUIDE.md의 해당 Agent 프롬프트를 기반으로
   → shared-memory.md의 EXPORT 정보를 주입
   → 이전 실패 정보가 있으면 에러 메시지 + 수정 지시 추가

3. Agent 결과를 어떻게 검증하는가?
   → Step 1: 파일 구조 검증 (필요한 파일이 모두 생성되었는가)
   → Step 2: 구문 검증 (Python syntax valid)
   → Step 3: 린트 (ruff check, mypy)
   → Step 4: 단위 테스트 (pytest tests/unit/)
   → Step 5: 통합 테스트 (pytest tests/integration/)
   → Step 6: 모듈 간 import 검증

4. 실패 시 어떻게 수정하는가?
   → 에러 종류별 전략:
     a) Syntax Error → 해당 Agent에게 에러 메시지 전달 + 재생성
     b) Import Error → interfaces.md 확인 → 인터페이스 불일치면 양쪽 Agent에게 수정 지시
     c) Test Failure → 실패한 테스트 + 트레이스백 전달 → Fix Agent 디스패치
     d) Type Error → mypy 에러 메시지 전달 → 해당 Agent 재생성
     e) 반복 실패 (3회+) → 접근 방식 변경 지시 (다른 라이브러리, 다른 패턴)

5. Phase 완료를 어떻게 판단하는가?
   → checklist.md의 해당 Phase 항목이 전부 [DONE]
   → 해당 Phase의 모든 테스트 통과
   → lint 에러 0건
```

## 5.3 Agent Dispatch 상세

단일 Agent 호출은 다음과 같이 구성된다:

```python
async def dispatch_agent(
    agent_id: str,
    task_ids: list[str],
    vibe_files: dict[str, str],
    workspace_files: dict[str, str],    # 기존 코드 파일
    previous_errors: list[dict] | None,  # 이전 실패 정보
    llm_router: LLMRouter,
) -> dict[str, str]:  # {파일경로: 코드내용}

    # 1. persona.md에서 해당 Agent 섹션 추출
    persona_section = extract_agent_section(vibe_files["persona.md"], agent_id)

    # 2. system prompt 조립
    system_prompt = assemble_system_prompt(
        persona=persona_section,
        conventions=vibe_files["conventions.md"],
        interfaces=extract_relevant_interfaces(vibe_files["interfaces.md"], agent_id),
    )

    # 3. user prompt 조립
    user_prompt = assemble_user_prompt(
        task_ids=task_ids,
        spec=extract_relevant_spec(vibe_files["spec.md"], agent_id),
        shared_memory=extract_exports_for(vibe_files["shared-memory.md"], agent_id),
        existing_code=workspace_files,
        previous_errors=previous_errors,
    )

    # 4. LLM 호출
    response = await llm_router.complete_structured(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=AgentCodeOutput,
        purpose="code_generation",
    )

    return response.files  # {파일경로: 코드내용}
```

## 5.4 Agent 코드 출력 포맷

Agent가 반환하는 구조화된 출력:

```python
class CodeFile(BaseModel):
    path: str          # "src/ingestion/parsers/pdf_parser.py"
    content: str       # 전체 파일 내용
    action: str        # "create" | "replace" | "append"

class TestFile(BaseModel):
    path: str          # "tests/unit/ingestion/test_pdf_parser.py"
    content: str

class SharedMemoryUpdate(BaseModel):
    agent_id: str
    type: str          # "EXPORT" | "INFO" | "REQUEST"
    target: str        # "ALL" | "Agent-E" 등
    subject: str
    content: str

class ChecklistUpdate(BaseModel):
    task_id: int
    status: str        # "[DONE]"
    date: str
    notes: str

class AgentCodeOutput(BaseModel):
    files: list[CodeFile]
    tests: list[TestFile]
    shared_memory_updates: list[SharedMemoryUpdate]
    checklist_updates: list[ChecklistUpdate]
    notes: str         # Agent의 작업 노트 (다음 Agent에게 전달)
```

## 5.5 Validation Pipeline

```
Agent 출력
     |
     v
[1. Structure Check]
  - 필요한 파일이 모두 포함되었는가
  - 파일 경로가 담당 디렉토리 내인가
  - __init__.py가 포함되었는가
     |
     v
[2. Syntax Check]
  python3 -m py_compile {file}
  각 파일이 문법적으로 유효한지
     |
     v
[3. Lint Check]
  ruff check src/ --select E,F,W,I
  mypy src/ --strict
     |
     v
[4. Import Check]
  python3 -c "import src.{module}"
  모듈이 정상 import되는지
  다른 모듈 인터페이스와 호환되는지
     |
     v
[5. Unit Test]
  pytest tests/unit/{module}/ -v --tb=short
     |
     v
[6. Integration Test] (Phase 완료 시에만)
  pytest tests/integration/ -v --tb=long
     |
     v
[전부 통과] → checklist 업데이트 → 다음 Task
[하나라도 실패] → Fix Agent 디스패치
```

## 5.6 Fix Agent 전략

```python
class FixStrategy(BaseModel):
    error_type: str
    strategy: str
    max_retries: int

FIX_STRATEGIES = [
    FixStrategy(
        error_type="SyntaxError",
        strategy="에러 라인 + 메시지를 Agent에게 전달, 해당 파일만 재생성",
        max_retries=3,
    ),
    FixStrategy(
        error_type="ImportError",
        strategy="interfaces.md 확인 후 import 경로 수정 또는 누락 함수 구현",
        max_retries=3,
    ),
    FixStrategy(
        error_type="TestFailure",
        strategy="실패 테스트의 traceback + 테스트 코드를 Agent에게 전달, 로직 수정",
        max_retries=5,
    ),
    FixStrategy(
        error_type="TypeError",
        strategy="mypy 에러 메시지 전달, 타입 힌트 수정",
        max_retries=3,
    ),
    FixStrategy(
        error_type="InterfaceMismatch",
        strategy="interfaces.md와 실제 코드 비교, 인터페이스 준수하도록 수정",
        max_retries=3,
    ),
    FixStrategy(
        error_type="RepeatedFailure",
        strategy="접근 방식 전체 변경: 다른 라이브러리/패턴 사용, spec.md 수정 후 재생성",
        max_retries=2,
    ),
]
```

---

# Part 6. Technology Stack

## 6.1 ARCHITECT System Stack

```
Core:
  - Python 3.12+
  - LangGraph 0.3+ (모든 Engine의 워크플로우)
  - LiteLLM 1.55+ (다중 LLM 라우팅)

LLM Models:
  Plan Engine:
    - claude-sonnet-4.6 (복잡한 아키텍처 설계)
    - Fallback: gpt-4o

  Generate Engine:
    - claude-sonnet-4.6 (MD 파일 생성)
    - Fallback: gpt-4o

  Execute Engine - Coding Agents:
    - claude-sonnet-4.6 (코드 생성, 정확도 중시)
    - Fallback: gpt-4o
    - Fix Agent: claude-sonnet-4.6 (디버깅 능력 중시)

  Execute Engine - Supervisor:
    - claude-haiku-4.5 (빠른 판단, 비용 효율)

Code Execution:
  - subprocess (lint, test 실행)
  - Docker (격리된 실행 환경, 선택)
  - testcontainers (DB 통합 테스트)

Storage:
  - 로컬 파일시스템 (Git repo)
  - Git (버전 관리, 자동 커밋)

Interface:
  - FastAPI (Plan Mode 웹 UI / API)
  - CLI (터미널 인터페이스)
  - WebSocket (실시간 진행률 스트리밍)
```

## 6.2 Dependencies

```toml
[project]
name = "architect"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # Core
    "langgraph>=0.3.0",
    "langchain-core>=0.3.0",
    "litellm>=1.55.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",

    # API (Plan Mode UI)
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=14.0",

    # Code Execution
    "ruff>=0.9.0",

    # Git
    "gitpython>=3.1.0",

    # Utilities
    "structlog>=24.4.0",
    "httpx>=0.28.0",
    "jinja2>=3.1.0",
    "rich>=13.9.0",       # CLI 출력
    "tiktoken>=0.8.0",    # 토큰 카운팅
]
```

---

# Part 7. Project Structure

```
architect/
|
+-- src/
|   +-- architect/
|   |   +-- __init__.py
|   |   +-- main.py                    # CLI / API 엔트리포인트
|   |   +-- config.py                  # 환경설정
|   |   |
|   |   +-- plan/                      # Plan Engine
|   |   |   +-- __init__.py
|   |   |   +-- engine.py              # LangGraph StateGraph
|   |   |   +-- states.py              # PlanState
|   |   |   +-- nodes/
|   |   |   |   +-- analyze.py         # 요구사항 분석
|   |   |   |   +-- choices.py         # 선택지 생성
|   |   |   |   +-- refine.py          # 명세 정제
|   |   |   |   +-- finalize.py        # Plan 문서 생성
|   |   |   +-- prompts/
|   |   |       +-- analyst.py
|   |   |       +-- architect.py
|   |   |       +-- choice_generator.py
|   |   |
|   |   +-- generate/                  # Generate Engine
|   |   |   +-- __init__.py
|   |   |   +-- engine.py              # LangGraph StateGraph
|   |   |   +-- states.py              # GenerateState
|   |   |   +-- nodes/
|   |   |   |   +-- decompose.py       # 모듈 분해
|   |   |   |   +-- assign.py          # Agent 할당
|   |   |   |   +-- gen_agent_md.py
|   |   |   |   +-- gen_persona.py
|   |   |   |   +-- gen_plan_md.py
|   |   |   |   +-- gen_spec.py
|   |   |   |   +-- gen_checklist.py
|   |   |   |   +-- gen_interfaces.py
|   |   |   |   +-- gen_conventions.py
|   |   |   |   +-- gen_shared_memory.py
|   |   |   |   +-- gen_operation_guide.py
|   |   |   |   +-- validate.py        # 정합성 검증
|   |   |   +-- prompts/
|   |   |   +-- templates/             # Jinja2 기본 템플릿
|   |   |
|   |   +-- execute/                   # Execute Engine
|   |   |   +-- __init__.py
|   |   |   +-- engine.py              # LangGraph StateGraph (Supervisor Loop)
|   |   |   +-- states.py              # ExecuteState
|   |   |   +-- supervisor.py          # 판단 로직
|   |   |   +-- dispatcher.py          # Agent 디스패치
|   |   |   +-- validator.py           # 코드 검증 파이프라인
|   |   |   +-- fixer.py               # Fix Agent 전략
|   |   |   +-- workspace.py           # 파일시스템 + Git 관리
|   |   |   +-- prompts/
|   |   |       +-- agent_system.py    # Agent system prompt 조립
|   |   |       +-- agent_user.py      # Agent user prompt 조립
|   |   |       +-- fix_prompt.py      # Fix Agent 프롬프트
|   |   |
|   |   +-- llm/                       # LLM 공통
|   |   |   +-- router.py              # LiteLLM 래퍼
|   |   |   +-- models.py              # 모델 설정
|   |   |   +-- cost_tracker.py        # 비용 추적
|   |   |
|   |   +-- core/                      # 공통
|   |   |   +-- models.py              # AgentCodeOutput 등
|   |   |   +-- exceptions.py
|   |   |   +-- logging.py
|   |   |
|   |   +-- api/                       # Plan Mode 웹 UI
|   |       +-- app.py                 # FastAPI 앱
|   |       +-- routes/
|   |       |   +-- plan.py            # Plan 대화 API
|   |       |   +-- execute.py         # 실행 제어 API
|   |       |   +-- status.py          # 진행률 API
|   |       +-- ws/
|   |           +-- progress.py        # WebSocket 진행률 스트리밍
|   |
|   +-- templates/                     # MD 파일 기본 템플릿
|       +-- agent.md.j2
|       +-- persona.md.j2
|       +-- plan.md.j2
|       +-- spec.md.j2
|       +-- checklist.md.j2
|       +-- interfaces.md.j2
|       +-- conventions.md.j2
|       +-- shared-memory.md.j2
|
+-- tests/
|   +-- unit/
|   +-- integration/
|   +-- fixtures/
|
+-- pyproject.toml
+-- README.md
```

---

# Part 8. Detailed Node Implementations

## 8.1 Plan Engine Nodes

### analyze_request

```python
async def analyze_request(state: PlanState) -> PlanState:
    """사용자 요구사항을 분석하여 도메인, 기능, 유형을 파악한다."""

    prompt = f"""
    Analyze the following software development request:

    "{state['user_request']}"

    Extract and return JSON:
    {{
        "domain": "프로젝트 도메인 (예: Enterprise Data, E-commerce, ...)",
        "project_type": "Backend API | Frontend App | Full Stack | CLI | Library",
        "core_features": ["기능1", "기능2", ...],
        "implied_requirements": ["명시되지 않았지만 필요한 것들"],
        "complexity": "small | medium | large",
        "estimated_agents": 3-8,
        "initial_questions": ["확인해야 할 질문들"]
    }}
    """

    analysis = await llm_router.complete_structured(
        messages=[{"role": "user", "content": prompt}],
        response_model=DomainAnalysis,
        purpose="plan_analysis",
    )

    state["domain_analysis"] = analysis.model_dump()
    state["open_questions"] = analysis.initial_questions
    return state
```

### present_choices

```python
async def present_choices(state: PlanState) -> PlanState:
    """현재 단계에서 사용자에게 선택지를 제시한다."""

    # 다음에 결정해야 할 항목 결정
    next_topic = determine_next_decision(state)

    if next_topic is None:
        # 모든 결정 완료 → Plan 생성으로
        state["open_questions"] = []
        return state

    prompt = f"""
    Context:
    - Domain: {state['domain_analysis']['domain']}
    - Type: {state['domain_analysis']['project_type']}
    - Decisions so far: {json.dumps(state['decisions'], ensure_ascii=False)}

    Generate 2-4 choices for: {next_topic['topic']}

    Return JSON array of choices, each with:
    - id: "A", "B", "C", "D"
    - label: 짧은 이름
    - description: 설명
    - pros: [장점]
    - cons: [단점]
    - recommended: boolean
    - reason: 권장 이유 (recommended=true인 경우)
    """

    choices = await llm_router.complete_structured(
        messages=[{"role": "user", "content": prompt}],
        response_model=ChoiceList,
        purpose="plan_choices",
    )

    # 대화 이력에 추가 (UI로 전달)
    state["conversation_history"].append({
        "role": "assistant",
        "type": "choices",
        "topic": next_topic["topic"],
        "choices": choices.model_dump(),
    })

    return state
```

## 8.2 Execute Engine Nodes

### dispatch_agents

```python
async def dispatch_agents(state: ExecuteState) -> ExecuteState:
    """현재 Phase의 Agent들을 병렬 디스패치한다."""

    agents_to_dispatch = state["active_agents"]
    tasks = []

    for agent_info in agents_to_dispatch:
        agent_id = agent_info["id"]
        task_ids = agent_info["tasks"]

        # 이전 실패 정보 확인
        previous_errors = [
            f for f in state["failed_tasks"]
            if f["agent_id"] == agent_id
        ]

        tasks.append(
            dispatch_single_agent(
                agent_id=agent_id,
                task_ids=task_ids,
                vibe_files=state["vibe_files"],
                workspace_path=state["workspace_path"],
                previous_errors=previous_errors if previous_errors else None,
            )
        )

    # 병렬 실행
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 수집
    for agent_info, result in zip(agents_to_dispatch, results):
        if isinstance(result, Exception):
            state["failed_tasks"].append({
                "agent_id": agent_info["id"],
                "error": str(result),
                "type": "DispatchError",
            })
        else:
            state["agent_outputs"][agent_info["id"]] = result

    return state
```

### evaluate_results

```python
async def evaluate_results(state: ExecuteState) -> ExecuteState:
    """테스트 결과를 분석하고 다음 행동을 결정한다."""

    lint_ok = state["lint_results"].get("exit_code") == 0
    tests_ok = state["test_results"].get("exit_code") == 0

    if lint_ok and tests_ok:
        state["phase_status"] = "complete"
        return state

    # 실패 분석
    failures = []

    if not lint_ok:
        lint_errors = parse_lint_output(state["lint_results"]["output"])
        for err in lint_errors:
            failures.append({
                "type": classify_error(err),
                "file": err["file"],
                "line": err["line"],
                "message": err["message"],
                "agent_id": find_responsible_agent(err["file"], state),
            })

    if not tests_ok:
        test_failures = parse_test_output(state["test_results"]["output"])
        for fail in test_failures:
            failures.append({
                "type": "TestFailure",
                "test": fail["test_name"],
                "traceback": fail["traceback"],
                "agent_id": find_responsible_agent(fail["file"], state),
            })

    state["failed_tasks"] = failures
    state["iteration"] += 1

    if state["iteration"] >= state["max_iterations"]:
        state["phase_status"] = "max_iterations_reached"
    else:
        state["phase_status"] = "fixing"

    return state
```

---

# Part 9. Safety & Limits

## 9.1 안전장치

| 장치 | 설명 | 기본값 |
|------|------|--------|
| Phase당 최대 반복 | Fix 루프 무한 방지 | 5회 |
| 전체 최대 반복 | 전체 시스템 무한 방지 | 20회 |
| Agent당 최대 토큰 | 단일 Agent 호출 제한 | 16,000 출력 토큰 |
| 총 비용 한도 | LLM API 비용 제한 | $50 (설정 가능) |
| 파일 크기 제한 | 단일 파일 최대 크기 | 500줄 (초과 시 분할 지시) |
| 실행 시간 제한 | 테스트 실행 타임아웃 | 300초 |
| 디스크 사용 제한 | 프로젝트 최대 크기 | 100MB |

## 9.2 에러 에스컬레이션

```
Level 1: Agent 자체 수정 (lint error, minor test failure)
  → Fix Agent 디스패치

Level 2: Supervisor 개입 (인터페이스 불일치, 반복 실패)
  → interfaces.md 재검토 → 관련 Agent 모두 재디스패치

Level 3: 접근 방식 변경 (3회 연속 같은 에러)
  → spec.md 해당 섹션 수정 → 다른 라이브러리/패턴으로 변경

Level 4: 사용자 개입 요청 (max iterations 도달)
  → 실패 보고서 생성 → 사용자에게 전달
  → 사용자 지시 후 재개
```

---

# Part 10. MD File System (Orchestration Layer)

ARCHITECT가 생성하는 .vibe/ 파일들의 역할과 Execute Engine과의 관계:

```
.vibe/
|
+-- agent.md
|   |-- Supervisor가 읽음: 디렉토리 구조, Agent Map, 의존 관계
|   |-- Agent가 읽음: 부팅 시퀀스, 파일 권한
|   +-- 자동 업데이트: 디렉토리 구조 변경 시
|
+-- persona.md
|   |-- Dispatcher가 읽음: Agent system prompt 조립에 사용
|   +-- 변경 없음 (Generate 시 확정)
|
+-- plan.md
|   |-- Supervisor가 읽음: Phase별 Task 목록, 우선순위
|   +-- 변경 없음 (Generate 시 확정)
|
+-- spec.md
|   |-- Dispatcher가 읽음: Agent user prompt에 기술 사양 주입
|   +-- 자동 업데이트: Level 3 에스컬레이션 시 (접근 방식 변경)
|
+-- checklist.md
|   |-- Supervisor가 읽음: 현재 진행 상태 판단
|   +-- 매 루프마다 자동 업데이트
|
+-- shared-memory.md
|   |-- Dispatcher가 읽음: Agent 간 EXPORT 정보 주입
|   +-- 매 Agent 완료마다 자동 업데이트
|
+-- interfaces.md
|   |-- Dispatcher가 읽음: Agent prompt에 인터페이스 계약 주입
|   |-- Validator가 읽음: 모듈 간 호환성 검증 기준
|   +-- 자동 업데이트: Level 2 에스컬레이션 시
|
+-- conventions.md
|   |-- Dispatcher가 읽음: Agent system prompt에 포함
|   +-- 변경 없음 (Generate 시 확정)
|
+-- OPERATION-GUIDE.md
|   |-- Dispatcher가 읽음: Agent 프롬프트 템플릿 원본
|   +-- 변경 없음 (Generate 시 확정)
|
+-- errors.md (신규 - Execute Engine 전용)
|   |-- Fixer가 읽음: 누적된 에러 패턴 분석
|   +-- 매 실패마다 자동 업데이트
|
+-- decisions.md (신규 - Plan Engine 전용)
    |-- Generate Engine이 읽음: 사용자의 모든 선택 기록
    +-- Plan Mode에서 자동 생성
```

---

# Part 11. Implementation Roadmap

## Phase 1: Plan Engine (2주)
- [ ] PlanState 정의
- [ ] analyze_request 노드
- [ ] present_choices 노드 (선택지 생성)
- [ ] refine_spec 노드 (사용자 응답 처리)
- [ ] generate_plan 노드 (Plan 문서 생성)
- [ ] CLI 인터페이스 (터미널 대화)
- [ ] Plan Engine 통합 테스트

## Phase 2: Generate Engine (2주)
- [ ] GenerateState 정의
- [ ] Module Decomposition 노드
- [ ] Agent Assignment 노드
- [ ] 8개 MD 파일 생성 노드 (각각)
- [ ] Jinja2 기본 템플릿
- [ ] Coherence Validation 노드
- [ ] Generate Engine 통합 테스트

## Phase 3: Execute Engine (3주)
- [ ] ExecuteState 정의
- [ ] Supervisor Loop (LangGraph)
- [ ] Agent Dispatcher (LLM 호출 + prompt 조립)
- [ ] Workspace Manager (파일시스템 + Git)
- [ ] Validation Pipeline (lint, test, import check)
- [ ] Fix Agent 전략 구현
- [ ] 안전장치 (반복 제한, 비용 제한)
- [ ] Execute Engine E2E 테스트

## Phase 4: Integration (1주)
- [ ] Plan → Generate → Execute 파이프라인 연결
- [ ] FastAPI 웹 UI (선택)
- [ ] WebSocket 진행률 스트리밍 (선택)
- [ ] 전체 E2E 테스트 (간단한 프로젝트로)

## Phase 5: Hardening (1주)
- [ ] 실제 프로젝트 3개로 검증
- [ ] 에러 패턴 분석 및 Fix 전략 보강
- [ ] 비용 최적화 (모델 선택, 토큰 관리)
- [ ] 문서화

---

# Part 12. Usage Example

```bash
# ARCHITECT 실행
$ architect new

ARCHITECT v0.1.0
================

어떤 프로그램을 만들고 싶으신가요?

> 기업의 DB, PDF, Word, Excel 문서를 수집해서 온톨로지를
> 구축하고 지식그래프를 만들어주는 REST API를 만들고 싶어.
> CI/CD에서 API로 호출 가능해야 하고, 새 문서가 추가되면
> 기존 지식그래프에 증분 업데이트 되어야 해.

[Plan Mode] 요구사항을 분석 중...

분석 결과:
  Domain: Enterprise Knowledge Management
  Type: Backend API
  Complexity: Large (예상 Agent 6개)
  Core Features:
    1. 멀티포맷 문서 파싱
    2. LLM 기반 온톨로지/엔티티 추출
    3. 지식그래프 저장/관리 (Neo4j)
    4. 증분 업데이트
    5. GraphRAG 검색
    6. CI/CD 통합 API

기술 스택을 선택해주세요:

  [A] Python + FastAPI + Neo4j + LangGraph (권장)
      장점: 풍부한 NLP 생태계, LangGraph 네이티브
      단점: GIL 제약 (비동기로 해결)

  [B] TypeScript + NestJS + Neptune
      장점: 타입 안전성, AWS 네이티브
      단점: LLM 생태계 약함

  [C] 직접 지정

> A

아키텍처 패턴을 선택해주세요:
  [A] Event-Driven Microservices (권장)
  [B] Monolithic API
  [C] Serverless

> A

[... 5-8개 추가 선택지 ...]

기술 명세서가 완성되었습니다.

[Plan Document Preview]
(전체 내용 표시)

승인하시겠습니까?
  [Y] 승인 — 자동 구현 시작
  [E] 수정 — 수정할 부분 지정
  [R] 거부 — 처음부터 다시

> Y

[Generate Mode] MD 파일 생성 중...
  agent.md .............. [DONE]
  persona.md ............ [DONE]
  plan.md ............... [DONE]
  spec.md ............... [DONE]
  checklist.md .......... [DONE]
  interfaces.md ......... [DONE]
  conventions.md ........ [DONE]
  shared-memory.md ...... [DONE]
  OPERATION-GUIDE.md .... [DONE]
  Coherence Check ....... [PASS]

[Execute Mode] 자동 구현을 시작합니다.

Phase 1/4: Foundation
  Dispatching: Agent-A (API), Agent-B (Ingestion), Agent-D (Graph), Agent-F (LLM)
  Agent-A: src/core/ 생성 중 ........... [DONE] 12 files
  Agent-B: src/ingestion/ 생성 중 ...... [DONE] 9 files
  Agent-D: src/graph/ 생성 중 .......... [DONE] 7 files
  Agent-F: src/llm/ 생성 중 ............ [DONE] 5 files
  Lint Check ........................... [PASS]
  Unit Tests ........................... [14/15 passed]
    FAIL: test_xlsx_parser — openpyxl import path error
  Fix Agent dispatched for Agent-B ..... [DONE]
  Unit Tests (retry) ................... [15/15 passed]
  Phase 1 Complete.

Phase 2/4: Intelligence
  Dispatching: Agent-C (Extraction), Agent-D (Incremental), Agent-E (Pipeline)
  [... 동일 패턴 ...]
  Phase 2 Complete.

Phase 3/4: Enterprise
  [...]
  Phase 3 Complete.

Phase 4/4: Hardening
  [...]
  Integration Tests .................... [PASS]
  Phase 4 Complete.

====================================
BUILD COMPLETE
====================================
Total Files: 87
Total Lines: 8,432
Test Coverage: 84%
LLM Cost: $12.47
Duration: 43 minutes

프로젝트가 ./okg-api/ 에 생성되었습니다.
```

---

# Appendix A: LangGraph State Diagrams

## Plan Engine

```
[START]
  |
  v
analyze_request
  |
  v
present_choices <---+
  |                 |
  v                 |
(user responds)     |
  |                 |
  v                 |
refine_spec --------+-- (더 결정할 것 있음)
  |
  | (모든 결정 완료)
  v
generate_plan
  |
  v
user_approval
  |         |
  v         v
[APPROVED] [MODIFY] --> refine_spec
```

## Execute Engine

```
[START]
  |
  v
read_state
  |
  v
select_phase
  |
  v
plan_dispatch
  |
  v
dispatch_agents (병렬)
  |
  v
collect_results
  |
  v
write_to_workspace
  |
  v
run_lint
  |
  v
run_tests
  |
  v
evaluate_results
  |         |
  v         v
[PASS]    [FAIL]
  |         |
  v         v
update_   fix_issues --> write_to_workspace (루프)
vibe_files
  |
  v
phase_complete
  |         |
  v         v
[NEXT]    [ALL DONE]
  |         |
  v         v
select_   [END]
phase
(루프)
```
