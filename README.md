<div align="center">

# ARCHITECT

**Autonomous Multi-Agent Coding Orchestration System**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![TypeScript](https://img.shields.io/badge/frontend-TypeScript-3178C6.svg)](architect/frontend/)

*Describe what you want to build. ARCHITECT plans, orchestrates, and delivers working code autonomously.*

</div>

---

## Overview

ARCHITECT transforms natural-language project descriptions into production-ready code through a three-stage pipeline:

1. **Plan** — Interactive conversation that captures requirements, technology decisions, and architecture constraints
2. **Generate** — Produces `.vibe/` orchestration files (Markdown specs) that define every detail agents need
3. **Execute** — A Supervisor loop dispatches specialized coding agents, reviews output, validates correctness, and self-heals on failure

No manual scaffolding, no boilerplate. You describe the system; ARCHITECT builds it.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Request                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Plan Engine          LangGraph StateGraph                  │
│  ─────────────────────────────────────────                  │
│  Multi-turn dialogue → technology decisions → plan.json     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Generate Engine      Jinja2 + LLM                          │
│  ─────────────────────────────────────────                  │
│  Plan → decompose modules → assign agents → .vibe/ files    │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Execute Engine       Supervisor Loop                       │
│  ─────────────────────────────────────────                  │
│  Planner → Assigner → Dispatcher → Reviewer → Validator     │
│  Self-healing: Diagnostician → Strategist → Fixer           │
│  Knowledge accumulation across sprints                      │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Deliverable          Working code in workspace/            │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the desktop/web UI)
- An LLM API key (OpenAI or Anthropic)

### Installation

```bash
git clone https://github.com/Kit4Some/AtomicVibe.git
cd AtomicVibe/architect
pip install -e ".[dev]"
```

### Usage

**Plan a project:**

```bash
architect plan "Build a TODO REST API with FastAPI and PostgreSQL"
```

The system walks you through architecture decisions interactively and produces a `plan.json`.

**Execute the pipeline:**

```bash
architect run --plan-file plan.json --workspace ./my-project
```

This generates `.vibe/` orchestration files and then autonomously produces working code.

**Launch the Web UI:**

```bash
architect serve --host 0.0.0.0 --port 18080
```

**Check job status:**

```bash
architect status --job-id <id>
```

## Agent System

Six specialized agents with strict directory ownership, enforced by the Supervisor's Reviewer role:

| Agent | Role | Owned Directories |
|-------|------|-------------------|
| **Agent-A** | Core Architect | `core/`, `config.py`, `main.py` |
| **Agent-L** | LLM Specialist | `llm/` |
| **Agent-P** | Plan Engineer | `plan/` |
| **Agent-G** | Generate Engineer | `generate/`, `templates/` |
| **Agent-E** | Execute Engineer | `execute/` |
| **Agent-U** | UI Engineer | `ui/`, `frontend/` |

Agents communicate through `.vibe/shared-memory.md` using structured protocols (`EXPORT`, `REQUEST`, `ALERT`) and are restricted to public APIs defined in `.vibe/interfaces.md`.

## `.vibe/` Orchestration Files

The `.vibe/` directory is the single source of truth for autonomous code generation:

| File | Purpose |
|------|---------|
| `spec.md` | Technical specification — models, APIs, validation rules |
| `plan.md` | Implementation plan with task breakdown and priorities |
| `agent.md` | Agent coordination rules, directory map, boot sequence |
| `persona.md` | Agent personalities, constraints, knowledge sources |
| `interfaces.md` | Module contracts and public API boundaries |
| `conventions.md` | Coding standards, style rules, naming conventions |
| `checklist.md` | Task progress tracker across sprints |
| `shared-memory.md` | Inter-agent communication channel |
| `knowledge.md` | Accumulated fix knowledge and best practices |
| `errors.md` | Error history for pattern detection and prevention |

## Desktop App

ARCHITECT includes an Electron + React desktop application with three resizable panels:

- **Side Panel** — File tree, `.vibe/` files, agent list, progress logs
- **Chat Panel** — Conversational planning and coding interface
- **Diff Panel** — Side-by-side diff viewer with Monaco editor

```bash
cd architect/frontend
npm install
npm run electron:dev     # Development mode
npm run electron:build   # Production build
```

## Configuration

All settings are configurable via environment variables (prefix `ARCHITECT_`) or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHITECT_OPENAI_API_KEY` | — | OpenAI API key |
| `ARCHITECT_ANTHROPIC_API_KEY` | — | Anthropic API key |
| `ARCHITECT_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Default LLM model |
| `ARCHITECT_MAX_COST_USD` | `50.0` | Maximum LLM cost budget (USD) |
| `ARCHITECT_MAX_TOTAL_ITERATIONS` | `30` | Max supervisor loop iterations |
| `ARCHITECT_MAX_SPRINT_ITERATIONS` | `5` | Max iterations per sprint |
| `ARCHITECT_WORKSPACE_PATH` | `./workspace` | Default output directory |
| `ARCHITECT_HOST` | `0.0.0.0` | Server bind host |
| `ARCHITECT_PORT` | `8080` | Server bind port |

## Testing

```bash
pytest tests/ -v                                    # All tests
pytest tests/unit/ -v                               # Unit tests
pytest tests/integration/ -v                        # Integration tests
pytest tests/ --cov=architect --cov-report=term-missing  # With coverage
```

## Project Structure

```
architect/
├── src/architect/
│   ├── core/           # Shared models, exceptions, logging
│   ├── llm/            # LLM router, cost tracking, model tiers
│   ├── plan/           # Plan Engine — interactive planning
│   ├── generate/       # Generate Engine — .vibe/ file production
│   ├── execute/        # Execute Engine — supervisor loop & agents
│   └── ui/             # FastAPI backend, WebSocket, routes
├── frontend/           # Electron + React + TypeScript + Tailwind
└── tests/              # pytest (unit + integration)
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).
