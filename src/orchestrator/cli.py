"""CLI interface for the orchestrator."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# Load environment variables from .env file
load_dotenv()

console = Console()


def _load_config(config_path: Optional[Path]) -> dict:
    """Load configuration from file or use default."""
    import yaml

    if config_path is None:
        config_path = Path("config/default.yaml")

    if not config_path.exists():
        console.print(f"[yellow]Warning: Config file not found at {config_path}[/yellow]")
        return {}

    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        return {}


async def _run_orchestrator(config: dict) -> None:
    """Run the orchestrator with given configuration."""
    from orchestrator.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(config)
    await orchestrator.run()


async def _run_interactive(config: dict) -> None:
    """Run orchestrator in interactive chat mode."""
    from orchestrator.core.orchestrator import Orchestrator

    console.print(Panel("Interactive Mode - Type 'exit' or 'quit' to stop", title="Orchestrator"))

    orchestrator = Orchestrator(config)
    await orchestrator.initialize()

    # Setup prompt session with history
    history_file = config.get("cli", {}).get("history_file", "./.orchestrator/history")
    Path(history_file).parent.mkdir(parents=True, exist_ok=True)

    session: PromptSession[str] = PromptSession(history=FileHistory(history_file))

    try:
        while True:
            try:
                # Get user input
                user_input = await session.prompt_async("orchestrator> ")

                if not user_input.strip():
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    if Confirm.ask("Are you sure you want to exit?"):
                        break
                    continue

                # Process input with orchestrator
                # Result is now displayed via DisplayHook in real-time
                await orchestrator.process_input(user_input)

            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    finally:
        await orchestrator.shutdown()


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path]) -> None:
    """Simple Orchestrator - A lightweight CLI Agent Orchestrator."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start the orchestrator."""
    console.print(Panel("Starting orchestrator...", title="Orchestrator"))

    config_path = ctx.obj.get("config")
    config = _load_config(config_path)

    try:
        asyncio.run(_run_orchestrator(config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@cli.command()
@click.pass_context
def chat(ctx: click.Context) -> None:
    """Start orchestrator in interactive chat mode."""
    config_path = ctx.obj.get("config")
    config = _load_config(config_path)

    try:
        asyncio.run(_run_interactive(config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@cli.command()
@click.pass_context
def test(ctx: click.Context) -> None:
    """Start orchestrator in test mode with isolated workspace (Phase 3.5).

    This mode ensures all Agent operations happen in an isolated workspace
    (.orchestrator/workspace/) to prevent pollution of project files.
    """
    config_path = ctx.obj.get("config")
    config = _load_config(config_path)

    # Ensure working_directory is set for test mode
    if "orchestrator" not in config:
        config["orchestrator"] = {}

    # Force workspace isolation in test mode
    config["orchestrator"]["working_directory"] = "./.orchestrator/workspace"

    console.print(
        Panel(
            "[bold cyan]Test Mode[/bold cyan]\n\n"
            "All Agent operations will be isolated in:\n"
            f"  [green]{Path('./.orchestrator/workspace').resolve()}[/green]\n\n"
            "Your project files are safe from modification.\n"
            "Type 'exit' or 'quit' to stop.",
            title="🧪 Orchestrator Test Mode",
            border_style="cyan",
        )
    )

    try:
        asyncio.run(_run_interactive(config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@cli.group()
def task() -> None:
    """Task management commands."""
    pass


@task.command("list")
def task_list() -> None:
    """List all tasks."""
    console.print("[yellow]Not implemented yet[/yellow]")


@task.command("add")
@click.argument("description")
def task_add(description: str) -> None:
    """Add a new task."""
    console.print(f"Adding task: {description}")
    console.print("[yellow]Not implemented yet[/yellow]")


@task.command("status")
@click.argument("task_id")
def task_status(task_id: str) -> None:
    """Show task status."""
    console.print(f"Task status for: {task_id}")
    console.print("[yellow]Not implemented yet[/yellow]")


@cli.group()
def tool() -> None:
    """Tool management commands."""
    pass


@tool.command("list")
def tool_list() -> None:
    """List all available tools."""
    console.print("[yellow]Not implemented yet[/yellow]")


@tool.command("info")
@click.argument("tool_name")
def tool_info(tool_name: str) -> None:
    """Show information about a tool."""
    console.print(f"Tool info for: {tool_name}")
    console.print("[yellow]Not implemented yet[/yellow]")


@cli.group()
def skill() -> None:
    """Skill management commands."""
    pass


@skill.command("list")
def skill_list() -> None:
    """List all available skills."""
    console.print("[yellow]Not implemented yet[/yellow]")


@skill.command("show")
@click.argument("skill_name")
def skill_show(skill_name: str) -> None:
    """Display SKILL.md content for a skill."""
    console.print(f"Skill: {skill_name}")
    console.print("[yellow]Not implemented yet[/yellow]")


@skill.command("create")
@click.argument("name")
def skill_create(name: str) -> None:
    """Create a new skill skeleton in user_extensions/skills/."""
    console.print(f"Creating skill: {name}")
    console.print("[yellow]Not implemented yet[/yellow]")


@cli.group()
def hook() -> None:
    """Hook management commands."""
    pass


@hook.command("list")
def hook_list() -> None:
    """List all hooks."""
    console.print("[yellow]Not implemented yet[/yellow]")


@hook.command("enable")
@click.argument("hook_name")
def hook_enable(hook_name: str) -> None:
    """Enable a hook."""
    console.print(f"Enabling hook: {hook_name}")
    console.print("[yellow]Not implemented yet[/yellow]")


@hook.command("disable")
@click.argument("hook_name")
def hook_disable(hook_name: str) -> None:
    """Disable a hook."""
    console.print(f"Disabling hook: {hook_name}")
    console.print("[yellow]Not implemented yet[/yellow]")


@cli.group()
def state() -> None:
    """State management commands."""
    pass


@state.command("show")
def state_show() -> None:
    """Show current orchestrator state."""
    console.print("[yellow]Not implemented yet[/yellow]")


@state.command("clear")
def state_clear() -> None:
    """Clear orchestrator state."""
    console.print("[yellow]Not implemented yet[/yellow]")


@state.command("export")
@click.argument("path", type=click.Path(path_type=Path))
def state_export(path: Path) -> None:
    """Export orchestrator state to a file."""
    console.print(f"Exporting state to: {path}")
    console.print("[yellow]Not implemented yet[/yellow]")


def main() -> None:
    """Main entry point."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
