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
    from orchestrator.display_stream import StreamingDisplayManager
    from orchestrator.display import set_display_manager

    # Check if streaming display is enabled (default: true)
    use_streaming = config.get("cli", {}).get("use_streaming_display", True)

    # Initialize display manager
    if use_streaming:
        display = StreamingDisplayManager()
        set_display_manager(display)
    # else: display manager will be initialized in orchestrator.initialize()

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
                # Get user input with colored mode indicator (Phase 6A+)
                if orchestrator.mode_manager:
                    mode = orchestrator.mode_manager.current_mode
                    mode_name = mode.value.upper()

                    # Map mode colors to ANSI color names
                    if mode.value == "ask":
                        color_tag = "ansicyan"
                    elif mode.value == "plan":
                        color_tag = "ansiyellow"
                    elif mode.value == "execute":
                        color_tag = "ansigreen"
                    else:
                        color_tag = "ansiwhite"

                    from prompt_toolkit.formatted_text import HTML
                    prompt_text = f"orchestrator [<b><{color_tag}>{mode_name}</{color_tag}></b>]> "
                    user_input = await session.prompt_async(HTML(prompt_text))
                else:
                    user_input = await session.prompt_async("orchestrator> ")

                if not user_input.strip():
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    if Confirm.ask("Are you sure you want to exit?"):
                        break
                    continue

                # Phase 6A+: Handle slash commands
                if user_input.startswith("/"):
                    command_parts = user_input[1:].split()
                    command = command_parts[0].lower() if command_parts else ""

                    if command == "mode":
                        if len(command_parts) < 2:
                            console.print("[yellow]Usage: /mode <ask|plan|execute>[/yellow]")
                            continue

                        mode_str = command_parts[1].lower()
                        try:
                            from orchestrator.modes.models import ExecutionMode

                            mode = ExecutionMode(mode_str)
                            orchestrator.set_mode(mode)
                            console.print(f"[green]✓ Switched to {mode.value.upper()} mode[/green]")
                        except ValueError:
                            console.print(
                                f"[red]Invalid mode: {mode_str}. Use: ask, plan, or execute[/red]"
                            )
                        continue

                    elif command == "session":
                        # Show session info
                        if orchestrator.mode_manager:
                            mode = orchestrator.mode_manager.current_mode
                            console.print(f"[cyan]Current Mode:[/cyan] {mode.value.upper()}")
                        if orchestrator.workspace:
                            console.print(
                                f"[cyan]Session ID:[/cyan] {orchestrator.workspace.session_id}"
                            )
                        continue

                    elif command == "help":
                        console.print(
                            """[cyan]Available Commands:[/cyan]
  /mode <ask|plan|execute>  - Switch execution mode
  /session                   - Show current session info
  /help                      - Show this help message
  exit, quit                 - Exit orchestrator
"""
                        )
                        continue

                    else:
                        console.print(f"[yellow]Unknown command: /{command}[/yellow]")
                        console.print("[yellow]Type /help for available commands[/yellow]")
                        continue

                # NEW (Phase 5B): Add user message to workspace conversation
                if orchestrator.workspace:
                    orchestrator.workspace.add_user_message(user_input)

                # Process input with orchestrator
                result = await orchestrator.process_input(user_input)

                # NEW (Phase 5B): Add assistant response to workspace conversation
                if orchestrator.workspace and result:
                    orchestrator.workspace.add_assistant_message(result)

                # UX Enhancement: Auto-prompt to execute after planning (Phase 6A+)
                if orchestrator.mode_manager and orchestrator.mode_manager.current_mode.value == "plan":
                    # Always show options after PLAN mode response
                    console.print("\n[bold yellow]What would you like to do next?[/bold yellow]")
                    console.print("  [cyan]1.[/cyan] Execute plan directly (switch to EXECUTE mode)")
                    console.print("  [cyan]2.[/cyan] Continue planning (stay in PLAN mode for discussion)")

                    choice_prompt = await session.prompt_async(
                        HTML("<ansiyellow>Choose option (1/2): </ansiyellow>")
                    )

                    if choice_prompt.strip() == "1":
                        # Check if there are pending tasks from planning
                        from orchestrator.tasks.models import TaskStatus
                        pending_tasks = await orchestrator.task_manager.list_tasks(status=TaskStatus.PENDING)

                        # Switch to EXECUTE mode
                        from orchestrator.modes.models import ExecutionMode
                        orchestrator.set_mode(ExecutionMode.EXECUTE)
                        console.print("[green]✓ Switched to EXECUTE mode[/green]")

                        if pending_tasks:
                            # Execute all pending tasks
                            console.print("\n[bold green]Starting execution...[/bold green]\n")
                            exec_result = await orchestrator._execute_all_pending_tasks()

                            if orchestrator.workspace and exec_result:
                                orchestrator.workspace.add_assistant_message(exec_result)
                        else:
                            # No pending tasks - ready for direct execution
                            console.print("\n[green]Ready to execute. Please enter your next command.[/green]")
                    else:
                        # Option 2 or any other input - continue planning
                        console.print("[yellow]Continuing in PLAN mode...[/yellow]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use Ctrl+D to exit[/yellow]")
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


@cli.group()
@click.pass_context
def workspace(ctx: click.Context) -> None:
    """Workspace management commands (Phase 5B)."""
    # Load config for workspace commands
    config_path = ctx.obj.get("config")
    ctx.obj["loaded_config"] = _load_config(config_path)


@workspace.command("list")
@click.pass_context
def workspace_list(ctx: click.Context) -> None:
    """List all workspaces."""
    from datetime import datetime
    from pathlib import Path
    from rich.table import Table
    from orchestrator.workspace.state import WorkspaceManager

    config = ctx.obj.get("loaded_config", {})
    workspace_config = config.get("workspace", {})
    workspace_dir = workspace_config.get("workspace_dir", ".orchestrator/workspace")

    manager = WorkspaceManager(workspace_dir)
    workspaces = []

    for workspace_file in manager.workspace_dir.glob("*.json"):
        try:
            stat = workspace_file.stat()
            workspaces.append({
                "session_id": workspace_file.stem,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size_kb": stat.st_size / 1024
            })
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {workspace_file.name}: {e}[/yellow]")

    if not workspaces:
        console.print("[yellow]No workspaces found[/yellow]")
        return

    # Display as table
    table = Table(title="Workspaces")
    table.add_column("Session ID", style="cyan")
    table.add_column("Last Modified", style="green")
    table.add_column("Size (KB)", justify="right", style="yellow")

    for ws in sorted(workspaces, key=lambda x: x['modified'], reverse=True):
        table.add_row(
            ws['session_id'],
            ws['modified'].strftime("%Y-%m-%d %H:%M:%S"),
            f"{ws['size_kb']:.2f}"
        )

    console.print(table)


@workspace.command("delete")
@click.argument("session_id")
@click.pass_context
def workspace_delete(ctx: click.Context, session_id: str) -> None:
    """Delete specific workspace."""
    from orchestrator.workspace.state import WorkspaceManager

    config = ctx.obj.get("loaded_config", {})
    workspace_config = config.get("workspace", {})
    workspace_dir = workspace_config.get("workspace_dir", ".orchestrator/workspace")

    manager = WorkspaceManager(workspace_dir)
    workspace_file = manager.workspace_dir / f"{session_id}.json"

    if not workspace_file.exists():
        console.print(f"[red]Workspace not found: {session_id}[/red]")
        return

    if Confirm.ask(f"Delete workspace {session_id}?"):
        try:
            workspace_file.unlink()
            console.print(f"[green]Deleted workspace: {session_id}[/green]")
        except Exception as e:
            console.print(f"[red]Error deleting workspace: {e}[/red]")
    else:
        console.print("[yellow]Deletion cancelled[/yellow]")


@workspace.command("purge")
@click.option("--older-than", type=int, default=365, help="Delete workspaces older than N days")
@click.pass_context
def workspace_purge(ctx: click.Context, older_than: int) -> None:
    """Purge old workspaces."""
    from orchestrator.workspace.state import WorkspaceManager
    from orchestrator.workspace.lifecycle import WorkspaceLifecycleManager

    config = ctx.obj.get("loaded_config", {})
    workspace_config = config.get("workspace", {})
    workspace_dir = workspace_config.get("workspace_dir", ".orchestrator/workspace")

    manager = WorkspaceManager(workspace_dir)
    lifecycle = WorkspaceLifecycleManager(manager, None)

    if Confirm.ask(f"Delete workspaces older than {older_than} days?"):
        try:
            count = lifecycle.cleanup_old_workspaces(days=older_than)
            console.print(f"[green]Purged {count} workspace(s)[/green]")
        except Exception as e:
            console.print(f"[red]Error during purge: {e}[/red]")
    else:
        console.print("[yellow]Purge cancelled[/yellow]")


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
