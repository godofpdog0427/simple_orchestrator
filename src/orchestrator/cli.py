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
@click.pass_context
def skill(ctx: click.Context) -> None:
    """Skill management commands (Phase 4A)."""
    # Load config for skill commands
    config_path = ctx.obj.get("config")
    ctx.obj["loaded_config"] = _load_config(config_path)


@skill.command("list")
@click.option("--tag", "-t", multiple=True, help="Filter by tags")
@click.option("--tool", multiple=True, help="Filter by required tools")
@click.pass_context
def skill_list(ctx: click.Context, tag: tuple[str, ...], tool: tuple[str, ...]) -> None:
    """List all available skills."""
    from rich.table import Table

    config = ctx.obj.get("loaded_config", {})

    # Initialize skill registry
    from orchestrator.skills.registry import SkillRegistry

    skill_config = config.get("skills", {})
    registry = SkillRegistry(skill_config)

    # Synchronously initialize
    import asyncio
    asyncio.run(registry.initialize())

    # Get skills
    if tag:
        skills = registry.search_by_tags(list(tag))
    elif tool:
        skills = registry.search_by_tools(list(tool))
    else:
        skills = registry.list_all()

    if not skills:
        console.print("[yellow]No skills found[/yellow]")
        return

    # Display table
    table = Table(title="📚 Available Skills", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", width=20)
    table.add_column("Description", style="white", width=40)
    table.add_column("Tools", style="green", width=20)
    table.add_column("Tags", style="yellow", width=20)

    for skill in skills:
        table.add_row(
            skill.metadata.name,
            skill.metadata.description,
            ", ".join(skill.metadata.tools_required[:3]),  # Limit display
            ", ".join(skill.metadata.tags[:3])  # Limit display
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(skills)} skill(s)[/dim]")


@skill.command("show")
@click.argument("skill_name")
@click.pass_context
def skill_show(ctx: click.Context, skill_name: str) -> None:
    """Display SKILL.md content for a skill."""
    from rich.markdown import Markdown
    from rich.panel import Panel

    config = ctx.obj.get("loaded_config", {})

    # Initialize skill registry
    from orchestrator.skills.registry import SkillRegistry

    skill_config = config.get("skills", {})
    registry = SkillRegistry(skill_config)

    import asyncio
    asyncio.run(registry.initialize())

    # Get skill
    skill = registry.get(skill_name)

    if not skill:
        console.print(f"[red]Skill not found: {skill_name}[/red]")
        return

    # Display metadata
    metadata_text = f"""**Name**: {skill.metadata.name}
**Description**: {skill.metadata.description}
**Version**: {skill.metadata.version}
**Priority**: {skill.metadata.priority}
**Tools Required**: {', '.join(skill.metadata.tools_required)}
**Tags**: {', '.join(skill.metadata.tags)}
**File**: {skill.file_path}"""

    console.print(Panel(metadata_text, title="Skill Metadata", border_style="cyan"))
    console.print()

    # Display content
    md = Markdown(skill.content)
    console.print(Panel(md, title="Skill Instructions", border_style="green"))


@skill.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Skill description")
@click.option("--tools", "-t", multiple=True, help="Required tools")
@click.option("--tags", multiple=True, help="Skill tags")
@click.pass_context
def skill_create(ctx: click.Context, name: str, description: str, tools: tuple[str, ...], tags: tuple[str, ...]) -> None:
    """Create a new skill skeleton in user_extensions/skills/."""
    from pathlib import Path
    from orchestrator.skills.models import create_skill_template

    config = ctx.obj.get("loaded_config", {})

    # Get user skills directory
    user_path = config.get("skills", {}).get("user_path", "user_extensions/skills")
    skill_dir = Path(user_path) / name
    skill_file = skill_dir / "SKILL.md"

    # Check if skill already exists
    if skill_file.exists():
        console.print(f"[red]Skill already exists: {skill_file}[/red]")
        return

    # Create directory
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Generate template
    template = create_skill_template(
        name=name,
        description=description or f"Description for {name}",
        tools_required=list(tools) if tools else [],
        tags=list(tags) if tags else []
    )

    # Write file
    skill_file.write_text(template, encoding="utf-8")

    console.print(f"[green]✓[/green] Created skill: {skill_file}")
    console.print(f"\nEdit the file to customize the skill instructions:")
    console.print(f"  {skill_file}")


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
