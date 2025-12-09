"""
CLI interface for Claude Swarm.
"""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from claude_swarm.agents.base import AgentType
from claude_swarm.config import detect_project_type, init_config, load_config
from claude_swarm.orchestrator import Orchestrator

console = Console()


@click.group()
@click.version_option()
def main():
    """Claude Swarm - Multi-agent orchestration for Claude Code."""
    pass


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
def init(force: bool):
    """Initialize Claude Swarm in the current project."""
    try:
        config_path = init_config(force=force)
        project_type = detect_project_type(Path.cwd())

        console.print(
            Panel.fit(
                f"[green]✓ Claude Swarm initialized![/green]\n\n"
                f"Project type: [cyan]{project_type.value}[/cyan]\n"
                f"Config file: [dim]{config_path}[/dim]\n"
                f"Workspace: [dim].swarm/[/dim]\n\n"
                f"[dim]Edit .swarm.yaml to customize agent behavior.[/dim]",
                title="🐝 Swarm Ready",
            )
        )
    except FileExistsError:
        console.print("[yellow]Configuration already exists. Use --force to overwrite.[/yellow]")


@main.command()
def status():
    """Show current swarm status."""
    try:
        config = load_config()
        orchestrator = Orchestrator(config=config)

        # List sessions
        sessions = orchestrator.list_sessions()

        if not sessions:
            console.print("[dim]No sessions found. Start one with:[/dim] swarm run <task>")
            return

        table = Table(title="📋 Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Feature", style="white")
        table.add_column("Status", style="green")
        table.add_column("Updated", style="dim")

        for session in sessions[:10]:
            table.add_row(
                session["session_id"],
                (
                    session["feature"][:40] + "..."
                    if len(session["feature"]) > 40
                    else session["feature"]
                ),
                session["status"],
                session["updated"][:19],
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command()
@click.argument("task")
@click.option("--context", "-c", multiple=True, help="Context files to include")
@click.option(
    "--agent",
    "-a",
    type=click.Choice([a.value for a in AgentType]),
    default="coder",
    help="Agent to use",
)
@click.option("--no-pipeline", is_flag=True, help="Skip automatic review/test pipeline")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed agent output")
@click.option("--interactive", "-i", is_flag=True, help="Run agents in separate terminal tabs")
def run(task: str, context: tuple, agent: str, no_pipeline: bool, verbose: bool, interactive: bool):
    """Run a task with the swarm.

    Examples:
        swarm run "Add user authentication"
        swarm run "Fix the login bug" --agent debugger
        swarm run "Implement feature X" --context src/main.py
        swarm run "Add feature" -v  # verbose output
        swarm run "Add feature" -i  # interactive mode (separate terminals)
    """
    try:
        config = load_config()
        orchestrator = Orchestrator(config=config, verbose=verbose, interactive=interactive)

        context_files = list(context) if context else None
        agent_type = AgentType(agent)

        if interactive:
            console.print("[cyan]🖥️  Running in interactive mode - agents will open in separate terminals[/cyan]\n")

        if verbose:
            console.print("[cyan]📝 Verbose mode enabled[/cyan]\n")

        if no_pipeline or agent_type != AgentType.CODER:
            # Single agent execution
            if not interactive:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task(f"Running {agent_type.value} agent...", total=None)
                    result = orchestrator.invoke_agent(
                        agent_type,
                        task,
                        context_files=context_files,
                    )
            else:
                result = orchestrator.invoke_agent(
                    agent_type,
                    task,
                    context_files=context_files,
                )

            _display_result(result)
        else:
            # Full pipeline
            if not interactive:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task("Running development pipeline...", total=None)
                    results = orchestrator.run_pipeline(
                        task,
                        context_files=context_files,
                    )
            else:
                results = orchestrator.run_pipeline(
                    task,
                    context_files=context_files,
                )

            for name, result in results.items():
                _display_result(result, name)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


@main.command()
@click.argument("feature")
@click.option("--execute", "-e", is_flag=True, help="Execute the plan immediately")
def plan(feature: str, execute: bool):
    """Plan a feature implementation using the architect agent.

    Examples:
        swarm plan "User authentication with OAuth"
        swarm plan "Add payment processing" --execute
    """
    try:
        config = load_config()
        orchestrator = Orchestrator(config=config)

        console.print(f"[cyan]📐 Planning feature:[/cyan] {feature}\n")

        tasks = orchestrator.plan_feature(feature)

        if tasks:
            table = Table(title="📋 Implementation Plan")
            table.add_column("ID", style="cyan")
            table.add_column("Agent", style="green")
            table.add_column("Task", style="white")
            table.add_column("Depends On", style="dim")

            for task in tasks:
                table.add_row(
                    task.id,
                    task.agent_type.value,
                    (
                        task.description[:50] + "..."
                        if len(task.description) > 50
                        else task.description
                    ),
                    ", ".join(task.depends_on) if task.depends_on else "-",
                )

            console.print(table)

            if execute:
                console.print("\n[cyan]▶️  Executing plan...[/cyan]\n")
                results = orchestrator.execute_plan()

                for task_id, result in results.items():
                    _display_result(result, task_id)
            else:
                console.print("\n[dim]Run with --execute to execute the plan, or use:[/dim]")
                console.print(f"  swarm execute {orchestrator.state.session_id}")
        else:
            console.print(
                "[yellow]Could not generate a plan. Try a more specific description.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


@main.command()
@click.argument("session_id")
def execute(session_id: str):
    """Execute a planned session.

    Example:
        swarm execute 20241215_143022
    """
    try:
        config = load_config()
        orchestrator = Orchestrator(config=config)

        if not orchestrator.resume_session(session_id):
            console.print(f"[red]Session not found: {session_id}[/red]")
            return

        console.print(f"[cyan]▶️  Resuming session:[/cyan] {session_id}\n")

        results = orchestrator.execute_plan()

        for task_id, result in results.items():
            _display_result(result, task_id)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


@main.command()
def agents():
    """List available agents and their descriptions."""
    agents_info = [
        ("coder", "Writes clean, production-ready code", "✏️"),
        ("reviewer", "Reviews code for quality and correctness", "🔍"),
        ("security", "Audits code for security vulnerabilities", "🔒"),
        ("tester", "Writes comprehensive tests", "🧪"),
        ("docs", "Creates and updates documentation", "📚"),
        ("architect", "Plans implementations and architecture", "📐"),
        ("debugger", "Diagnoses and fixes bugs", "🐛"),
        ("mobile_ui", "Implements mobile UI (React Native)", "📱"),
        ("aws", "Handles AWS/cloud infrastructure", "☁️"),
    ]

    table = Table(title="🤖 Available Agents")
    table.add_column("", style="white", width=3)
    table.add_column("Agent", style="cyan")
    table.add_column("Description", style="white")

    for name, desc, emoji in agents_info:
        table.add_row(emoji, name, desc)

    console.print(table)

    console.print('\n[dim]Use agents with:[/dim] swarm run "task" --agent <agent_name>')


@main.command()
@click.option("--session", "-s", help="Session ID to show summaries for")
def summaries(session: str):
    """Show agent summaries from the current or specified session."""
    try:
        config = load_config()
        orchestrator = Orchestrator(config=config)

        if session:
            if not orchestrator.resume_session(session):
                console.print(f"[red]Session not found: {session}[/red]")
                return

        # Read summaries from workspace
        summaries_dir = orchestrator.workspace / "summaries"

        if not summaries_dir.exists():
            console.print("[dim]No summaries found.[/dim]")
            return

        for summary_file in sorted(summaries_dir.glob("*.json"))[-10:]:
            try:
                data = json.loads(summary_file.read_text())
                agent = data.get("agent_type", "unknown")
                success = "✓" if data.get("success") else "✗"
                summary = data.get("summary", "")[:200]

                console.print(
                    Panel(
                        f"{summary}",
                        title=f"{success} [{agent.upper()}] {summary_file.stem}",
                        border_style="green" if data.get("success") else "red",
                    )
                )
            except Exception:
                continue

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command()
def config():
    """Show current configuration."""
    try:
        cfg = load_config()

        console.print(
            Panel.fit(
                f"Project Type: [cyan]{cfg.project_type.value}[/cyan]\n"
                f"Workspace: [dim]{cfg.workspace_dir}[/dim]\n"
                f"Source Dirs: [dim]{', '.join(cfg.source_dirs)}[/dim]\n"
                f"Test Dirs: [dim]{', '.join(cfg.test_dirs)}[/dim]",
                title="⚙️  Configuration",
            )
        )

        # Show orchestrator settings
        console.print("\n[cyan]Orchestrator Settings:[/cyan]")
        console.print(f"  Max Context: {cfg.orchestrator.max_context_tokens} tokens")
        console.print(f"  Auto Pipeline: {cfg.orchestrator.auto_pipeline}")
        console.print(f"  Parallel Reviews: {cfg.orchestrator.parallel_reviews}")
        console.print(f"  Require Security: {cfg.orchestrator.require_security_pass}")
        console.print(f"  Require Tests: {cfg.orchestrator.require_tests}")

        # Show enabled agents
        console.print("\n[cyan]Agents:[/cyan]")
        for agent_type in AgentType:
            if agent_type.value in cfg.agents:
                enabled = cfg.agents[agent_type.value].enabled
                status = "[green]enabled[/green]" if enabled else "[red]disabled[/red]"
            else:
                status = "[green]enabled[/green] (default)"
            console.print(f"  {agent_type.value}: {status}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _display_result(result, label: str = None):
    """Display an agent result in a nice format."""
    title = f"{result.agent_type.value.upper()}"
    if label:
        title = f"{label} ({title})"

    status_icon = "✓" if result.success else "✗"
    if result.blocked:
        status_icon = "⛔"
        border_style = "red"
    elif result.success:
        border_style = "green"
    else:
        border_style = "yellow"

    content = f"{status_icon} {result.summary[:500]}"

    if result.files_changed:
        content += f"\n\n[dim]Changed:[/dim] {', '.join(result.files_changed[:5])}"

    if result.files_created:
        content += f"\n[dim]Created:[/dim] {', '.join(result.files_created[:5])}"

    if result.issues_found:
        content += f"\n\n[yellow]Issues: {len(result.issues_found)}[/yellow]"
        for issue in result.issues_found[:3]:
            severity = issue.get("severity", "info")
            desc = issue.get("description", "")[:100]
            content += f"\n  • [{severity}] {desc}"

    if result.blocked:
        content += f"\n\n[red]Blocked: {result.block_reason}[/red]"

    content += f"\n\n[dim]Time: {result.execution_time:.1f}s[/dim]"

    console.print(Panel(content, title=title, border_style=border_style))


if __name__ == "__main__":
    main()
