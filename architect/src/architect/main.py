"""CLI entry point for ARCHITECT using Typer."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="architect",
    help="ARCHITECT - Autonomous multi-agent coding orchestration system.",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_router() -> Any:
    """Create an LLMRouter from current settings."""
    from architect.config import get_settings
    from architect.llm import LLMRouter

    return LLMRouter(get_settings())


def _display_choices(choices: list[Any]) -> None:
    """Render choices as a rich table."""
    table = Table(title="Select an option", show_lines=True)
    table.add_column("ID", style="bold cyan", width=4)
    table.add_column("Label", style="bold")
    table.add_column("Description")
    table.add_column("Pros", style="green")
    table.add_column("Cons", style="red")
    table.add_column("", width=3)

    for c in choices:
        rec = "*" if c.recommended else ""
        table.add_row(
            c.id,
            c.label,
            c.description,
            "\n".join(f"+ {p}" for p in c.pros),
            "\n".join(f"- {co}" for co in c.cons),
            rec,
        )
    console.print(table)


def _display_plan_preview(plan_doc: str) -> None:
    """Show plan document as rendered Markdown."""
    console.print(Panel(Markdown(plan_doc), title="Plan Document", border_style="blue"))


async def _run_plan(description: str, output: Path) -> None:
    """Execute the Plan Mode conversation loop."""
    from architect.plan import PlanEngine

    router = _create_router()
    engine = PlanEngine(router)

    console.print(f"[bold blue]Plan Mode[/bold blue] - {description}\n")

    state = await engine.start(description)

    # Show initial analysis message
    for msg in state.get("conversation_history", []):
        if msg.get("role") == "assistant":
            console.print(Panel(msg.get("content", ""), border_style="dim"))

    while not engine.is_complete(state):
        if not engine.needs_user_input(state):
            state = await engine.respond(state, "")
            continue

        choices = engine.get_current_choices(state)
        if choices:
            _display_choices(choices)
            user_input = console.input("[bold]Your choice (ID or free text): [/bold]")
        elif state.get("current_step") == "wait_approval":
            plan_doc = engine.get_plan_document(state)
            if plan_doc:
                _display_plan_preview(plan_doc)
            user_input = console.input(
                "[bold]Approve this plan? (approve / reject / feedback): [/bold]"
            )
        else:
            user_input = console.input("[bold]> [/bold]")

        state = await engine.respond(state, user_input)

        # Show assistant responses
        history = state.get("conversation_history", [])
        if history and history[-1].get("role") == "assistant":
            console.print(Panel(history[-1].get("content", ""), border_style="dim"))

    # Save plan
    plan_data = {
        "plan_document": engine.get_plan_document(state),
        "decisions": state.get("decisions", []),
    }
    output.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]Plan saved to {output}[/bold green]")


async def _run_pipeline(plan_file: Path, workspace: Path) -> None:
    """Execute Generate + Execute pipeline."""
    from architect.execute import ExecuteEngine
    from architect.generate import GenerateEngine

    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    plan_document = plan_data["plan_document"]
    decisions = plan_data.get("decisions", [])

    router = _create_router()

    # --- Generate ---
    console.print("[bold yellow]Phase: Generate[/bold yellow] - Creating orchestration files...")
    gen_engine = GenerateEngine(router)
    vibe_path = str(workspace / ".vibe")
    vibe_files = await gen_engine.generate(plan_document, decisions, vibe_path)
    console.print(f"  Generated {len(vibe_files)} files")

    # --- Execute ---
    console.print("[bold yellow]Phase: Execute[/bold yellow] - Running Supervisor Loop...")
    exec_engine = ExecuteEngine(router, str(workspace))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing...", total=None)

        def _on_progress(event: str, data: dict[str, Any]) -> None:
            phase = data.get("current_phase", "?")
            sprint = data.get("current_sprint", "?")
            msg = data.get("message", event)
            progress.update(task, description=f"[P{phase}/S{sprint}] {msg}")

        exec_engine.on_progress(_on_progress)
        await exec_engine.run(vibe_files)

    # --- Summary ---
    status = exec_engine.get_status()
    console.print("\n[bold green]Execution Complete[/bold green]")
    summary = Table(title="Result Summary")
    summary.add_column("Key")
    summary.add_column("Value")
    summary.add_row("Status", str(status.get("system_status", "unknown")))
    summary.add_row("Phases", str(status.get("current_phase", "?")))
    summary.add_row("Sprints", str(status.get("current_sprint", "?")))
    summary.add_row("Iterations", str(status.get("total_iterations", "?")))
    summary.add_row("Cost (USD)", f"${status.get('cost_usd', 0):.2f}")
    console.print(summary)

    tree = exec_engine.get_file_tree()
    if tree:
        console.print(f"\n[dim]Generated {len(tree)} files in {workspace}[/dim]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def plan(
    description: Annotated[
        str,
        typer.Argument(help="Project description to start Plan Mode conversation."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output path for plan JSON."),
    ] = Path("plan.json"),
) -> None:
    """Start Plan Mode: interactive conversation to define project specification."""
    try:
        asyncio.run(_run_plan(description, output))
    except KeyboardInterrupt:
        console.print("\n[yellow]Plan Mode interrupted.[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def run(
    plan_file: Annotated[
        Path,
        typer.Option("--plan-file", help="Path to plan JSON from Plan Mode."),
    ],
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help="Workspace output directory."),
    ] = Path("./workspace"),
) -> None:
    """Run Generate + Execute pipeline for a given plan."""
    if not plan_file.exists():
        console.print(f"[red]Plan file not found: {plan_file}[/red]")
        raise typer.Exit(code=1)
    try:
        asyncio.run(_run_pipeline(plan_file, workspace))
    except KeyboardInterrupt:
        console.print("\n[yellow]Execution interrupted.[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def status(
    job_id: Annotated[
        str,
        typer.Option("--job-id", help="Job ID of a running execution."),
    ] = "",
) -> None:
    """Check progress status of a running job."""
    status_file = Path(".architect_status.json")
    if status_file.exists():
        data = json.loads(status_file.read_text(encoding="utf-8"))
        table = Table(title=f"Job Status: {job_id or 'latest'}")
        table.add_column("Key")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), str(v))
        console.print(table)
    else:
        console.print("[dim]No active job found.[/dim]")


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Server bind host.")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="Server bind port.")] = 18080,
) -> None:
    """Start the web UI server."""
    import uvicorn

    from architect.ui import create_app

    console.print(f"[bold magenta]Serve[/bold magenta] - http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    app()
