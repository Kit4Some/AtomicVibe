# ARCHITECT

Autonomous multi-agent coding orchestration system. Describe what you want to build through a conversational Plan Mode, and ARCHITECT generates orchestration files then autonomously dispatches coding agents to produce working code.

## Installation

```bash
cd architect
pip install -e ".[dev]"
```

Requires Python 3.12+.

## CLI Usage

### Plan Mode

Start an interactive conversation to define your project specification:

```bash
architect plan "Build a TODO REST API with FastAPI"
```

The system guides you through decisions (tech stack, architecture, features, deployment, etc.) and produces a plan document saved as `plan.json`.

Options:
- `--output / -o` : Output path for plan JSON (default: `plan.json`)

### Run Pipeline

Execute the Generate + Execute pipeline from a completed plan:

```bash
architect run --plan-file plan.json --workspace ./my-project
```

This will:
1. **Generate** orchestration files (`.vibe/` Markdown specs)
2. **Execute** the Supervisor Loop (autonomous coding agents produce working code)

Options:
- `--plan-file` : Path to plan JSON from Plan Mode (required)
- `--workspace / -w` : Output directory (default: `./workspace`)

### Check Status

```bash
architect status --job-id <id>
```

### Web UI

Start the web interface for a visual experience:

```bash
architect serve --host 0.0.0.0 --port 8080
```

Pages: Plan (chat + choices), Diff (code review), Execute (progress + controls), Preview (file tree + test results), Terminal (shell access).

## Architecture

```
User Request
    |
    v
[Plan Mode] --- Interactive conversation, decision choices
    |             Output: plan.json (plan_document + decisions)
    v
[Generate]  --- Plan -> .vibe/ orchestration files (11 Markdown files)
    |             Jinja2 templates + LLM content generation
    v
[Execute]   --- Supervisor Loop with 5 PM roles:
    |             Planner -> Assigner -> Dispatcher -> Reviewer -> Validator
    |             Self-healing: Diagnostician -> Strategist -> Fixer
    |             Knowledge accumulation across sprints
    v
[Deliver]   --- Generated code in workspace directory
                 Diff view, test results, file tree
```

### Engine Details

| Engine | Description | Key Class |
|--------|-------------|-----------|
| Plan | Multi-turn LLM conversation with structured choices | `PlanEngine` |
| Generate | Decompose plan into modules, assign agents, generate .vibe files | `GenerateEngine` |
| Execute | Supervisor loop: sprint planning, code generation, review, validation, self-healing | `ExecuteEngine` |

### Agent System

6 specialized agents with strict directory ownership:

| Agent | Role | Scope |
|-------|------|-------|
| Agent-A | Core Architect | `core/`, `config.py`, `main.py` |
| Agent-L | LLM Specialist | `llm/` |
| Agent-P | Plan Engineer | `plan/` |
| Agent-G | Generate Engineer | `generate/` |
| Agent-E | Execute Engineer | `execute/` |
| Agent-U | UI Engineer | `ui/`, `frontend/` |

### .vibe File System

The `.vibe/` directory contains orchestration files that define everything agents need to build the project:

| File | Purpose |
|------|---------|
| `agent.md` | Agent coordination rules, directory map, boot sequence |
| `persona.md` | Agent personalities, constraints, knowledge sources |
| `plan.md` | Implementation plan with task breakdown |
| `spec.md` | Technical specification (models, APIs, validation) |
| `checklist.md` | Task progress tracker |
| `interfaces.md` | Module contracts (public APIs between modules) |
| `conventions.md` | Coding standards and style rules |
| `shared-memory.md` | Inter-agent communication (EXPORT, REQUEST, ALERT) |
| `knowledge.md` | Accumulated fix knowledge and best practices |
| `errors.md` | Error history for pattern detection |

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=architect --cov-report=term-missing
```

## Configuration

All settings via environment variables (prefix `ARCHITECT_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHITECT_OPENAI_API_KEY` | (empty) | OpenAI API key |
| `ARCHITECT_ANTHROPIC_API_KEY` | (empty) | Anthropic API key |
| `ARCHITECT_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Default LLM model |
| `ARCHITECT_MAX_COST_USD` | `50.0` | Maximum LLM cost budget |
| `ARCHITECT_MAX_TOTAL_ITERATIONS` | `30` | Max supervisor iterations |
| `ARCHITECT_MAX_SPRINT_ITERATIONS` | `5` | Max iterations per sprint |
| `ARCHITECT_WORKSPACE_PATH` | `./workspace` | Default workspace directory |
| `ARCHITECT_HOST` | `0.0.0.0` | Web UI bind host |
| `ARCHITECT_PORT` | `8080` | Web UI bind port |
| `ARCHITECT_LOG_FORMAT` | `console` | Log format: `console` or `json` |

Or use a `.env` file in the project root.
