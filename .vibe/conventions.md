# conventions.md — Coding Standards

> Version: 2.0.0

---

## 1. Python Style
- Python 3.12+, ruff format, mypy strict
- snake_case (함수/변수), PascalCase (클래스), UPPER_SNAKE (상수)
- 타입 힌트 필수, `X | None` 사용
- import: stdlib -> third-party -> local (ruff I)
- line length: 100

## 2. Module Rules
- 모듈 간 import는 interfaces.md의 public API만
- `__init__.py`에 `__all__` 정의, 내부 구현은 `_` prefix
- 순환 import 금지

## 3. Error Handling
- ArchitectBaseError 상속
- partial failure 허용: `asyncio.gather(*tasks, return_exceptions=True)`
- structlog 구조화 로깅

## 4. LangGraph
- 모든 Engine: StateGraph + TypedDict
- 노드: State 입력 -> State 출력
- 분기: `add_conditional_edges()`

## 5. LLM
- 직접 호출 금지, `from src.architect.llm import LLMRouter` 경유
- `complete_structured(response_model=...)` 우선 사용
- 모든 호출에 purpose 필수

## 6. Frontend
- React + TypeScript strict mode
- Tailwind utility classes (인라인 스타일 금지)
- API 호출: fetch 래퍼 또는 tanstack-query
- WebSocket: 재연결 로직 포함

## 7. Testing
- 단위: LLM mock, 외부 서비스 mock
- 통합: 간단한 프로젝트로 전체 플로우
- 네이밍: `test_{동사}_{대상}_{시나리오}`

## 8. Git Commit
```
<type>(<scope>): <subject>
type: feat | fix | refactor | test | docs | chore
scope: core | plan | generate | execute | llm | ui
```
