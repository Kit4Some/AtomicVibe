# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ARCHITECT is an autonomous multi-agent coding orchestration system. Users describe what they want to build through a conversational Plan Mode, the system generates orchestration files (Markdown), then a Supervisor loop autonomously dispatches coding agents to produce working code.

## Key Directories

- `.vibe/` — Orchestration files: source of truth for architecture (`spec.md`, `interfaces.md`, `conventions.md`, `agent.md`, `plan.md`, `checklist.md`)
- `architect/src/architect/` — Python source (core/, llm/, plan/, generate/, execute/, ui/)
- `architect/frontend/` — React 18 + TypeScript + Tailwind 4 + Electron desktop app
- `architect/tests/` — pytest tests with unit/ and integration/ subdirectories

## Commands

All backend commands run from the `architect/` directory. Frontend commands from `architect/frontend/`.

```bash
# Backend install (hatchling-based)
cd architect && pip install -e ".[dev]"

# CLI
architect plan "project description"
architect run --plan-file plan.json --workspace ./workspace
architect status --job-id <job_id>
architect serve --host 0.0.0.0 --port 18080

# Tests
pytest tests/ -v
pytest tests/unit/test_plan_engine.py -v
pytest tests/unit/test_plan_engine.py -k "test_analyze" -v

# Lint and type check
ruff check src/
ruff format src/ --check
mypy src/ --strict

# Frontend (from architect/frontend/)
npm run dev              # Vite dev server (web mode, port 5173)
npm run build            # TypeScript check + Vite production build
npm run electron:dev     # Electron dev mode (auto-starts backend on port 18080)
npm run electron:build   # Electron production build + packaging
```

## Architecture

### Backend — Three LangGraph StateGraph Engines

1. **Plan Engine** (`plan/`): Multi-turn user dialogue → technology decisions → plan document
2. **Generate Engine** (`generate/`): Plan document → decompose modules → assign agents → generate `.vibe/` orchestration files (Jinja2 templates with custom delimiters)
3. **Execute Engine** (`execute/`): Supervisor loop with 5 roles (Planner, Assigner, Reviewer, Diagnostician, Strategist) → dispatches coding agents → validates → self-heals

### Frontend — Electron + React

Single-page unified layout (`App.tsx`) with three resizable panels:
- **SidePanel** — File tree, .vibe files, agent list, progress logs
- **ChatPanel** — Conversational planning and coding interface
- **DiffPanel** — Side-by-side diff viewer with Monaco editor

No client-side router — panel visibility is managed via React state.

**Electron main process** (`electron/main.ts`) spawns `architect serve --port 18080` as a child process, health-polls (500ms interval, 30s timeout) until ready, then opens a BrowserWindow. Preload script exposes `window.electronAPI.getBackendPort()` via IPC. Uses `electron-vite` for builds.

**Dual-mode API client** (`src/api/client.ts`): In Electron, axios hits `http://127.0.0.1:18080/api` directly. In web dev mode, Vite proxies `/api` → `http://localhost:18080`. WebSocket hook (`src/hooks/useWebSocket.ts`) follows the same pattern.

**State management**: React Context + useReducer (`AppContext.tsx`) holds `planId`, `jobId`, `apiKeyConfigured`, and `tier`.

**Backend routes** (`ui/routes/`): plan, vibe, execute, agents, diff, preview, settings. WebSocket routes in `ui/ws/` for progress and terminal.

### Key Patterns

**Node functions** — async functions returning dict updates merged into state. Dependencies injected via `functools.partial`:
```python
async def node_name(state: ExecuteStateV2, *, llm: LLMRouter, workspace: Workspace) -> dict[str, Any]:
    return {**updated_fields}

graph.add_node("node_name", functools.partial(node_name, llm=llm, workspace=ws))
```

**LLM calls** — always through `LLMRouter` (never call litellm directly). Every call requires a `purpose` string for model routing and cost tracking. Prefer `complete_structured(response_model=...)` for typed responses.

**Configuration** — `config.py` uses Pydantic `BaseSettings` with `ARCHITECT_` env prefix, `.env` file support, and `get_settings()` LRU-cached singleton.

**Exceptions** — all inherit from `ArchitectBaseError` with `message`, `detail`, `status_code` fields. Subclasses: `PlanError`, `GenerateError`, `ExecuteError` (→ `ValidationError`, `DispatchError`, `FixError`, `WorkspaceError`), `LLMError` (→ `LLMRateLimitError`, `LLMResponseParseError`, `LLMBudgetExceededError`), `UIError`.

**Logging** — `structlog` via `core.logging.get_logger(__name__)`. Uses `PrintLoggerFactory` (not stdlib), so `add_logger_name` processor is incompatible.

### Agent System

6 agents with strict directory ownership (enforced by Reviewer):

| Agent | Directories |
|-------|-------------|
| Agent-A (Core) | core/, config.py, main.py |
| Agent-L (LLM) | llm/ |
| Agent-P (Plan) | plan/ |
| Agent-G (Generate) | generate/, templates/ |
| Agent-E (Execute) | execute/ |
| Agent-U (UI) | ui/, frontend/ |

Inter-agent communication via `.vibe/shared-memory.md`. Module imports restricted to public APIs in `.vibe/interfaces.md`.

## Coding Conventions

- Python 3.12+, ruff (E/F/I/W, line-length 100), mypy strict
- Type hints required; `X | None` syntax, no `Optional`
- Imports: `from __future__ import annotations` first, then stdlib → third-party → local
- `__init__.py` must define `__all__`; internal implementations use `_` prefix
- Async all the way — all I/O is async; use `asyncio.gather(*tasks, return_exceptions=True)` for partial failure
- LangGraph: TypedDict states, `add_conditional_edges()` for branching
- Tests: `pytest-asyncio` (auto mode), `AsyncMock` for mocking, naming `test_{verb}_{target}_{scenario}`
- Frontend: TypeScript strict, Tailwind utilities only, WebSocket with reconnect, path alias `@/*` → `./src/*`
- Backend CORS allows `http://localhost:5173` (Vite) and `null` (Electron file://)

## Git Commit Format

```
<type>(<scope>): <subject>
type: feat | fix | refactor | test | docs | chore
scope: core | plan | generate | execute | llm | ui
```
