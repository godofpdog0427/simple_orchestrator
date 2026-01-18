"""Welcome screen builder for orchestrator CLI."""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.align import Align

from orchestrator.cli.mascot import SealMascot, MascotPose
from orchestrator.modes.models import ExecutionMode


class WelcomeScreen:
    """Builder for orchestrator welcome screen."""

    # Mode color mapping
    MODE_COLORS = {
        ExecutionMode.ASK: "cyan",
        ExecutionMode.PLAN: "yellow",
        ExecutionMode.EXECUTE: "green",
    }

    def __init__(self, console: Console):
        """Initialize welcome screen builder.

        Args:
            console: Rich console for display
        """
        self.console = console

    def display_welcome(
        self,
        mode: ExecutionMode,
        session_name: Optional[str] = None,
        task_progress: Optional[tuple[int, int]] = None,
        username: Optional[str] = None,
    ) -> None:
        """Display full welcome screen with mascot.

        Args:
            mode: Current execution mode
            session_name: Optional session name
            task_progress: Optional (current, total) task count
            username: Optional username for greeting
        """
        # Get mode color
        color = self.MODE_COLORS.get(mode, "white")

        # Build greeting text
        greeting = self._build_greeting(username)

        # Get mascot
        pose = MascotPose.WAVING if username else MascotPose.HAPPY
        mascot = SealMascot.get_colored_pose(pose, color)

        # Build status line
        status_parts = [f"Mode: [bold]{mode.value.upper()}[/bold]"]
        if session_name:
            status_parts.append(f"Session: {session_name}")
        if task_progress:
            current, total = task_progress
            status_parts.append(f"Task #{current}/{total}")
        status_line = " | ".join(status_parts)

        # Build help line
        help_line = "Type [yellow]/help[/yellow] for commands | [yellow]/quit[/yellow] to exit"

        # Combine all parts
        content = (
            f"\n{greeting}\n\n"
            f"{mascot}\n\n"
            f"{status_line}\n\n"
            f"{help_line}\n"
        )

        # Display panel
        panel = Panel(
            Align.center(content),
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)

    def _build_greeting(self, username: Optional[str] = None) -> str:
        """Build greeting text.

        Args:
            username: Optional username

        Returns:
            Greeting string
        """
        if username:
            return f"Welcome back {username}! 👋"
        else:
            return "Welcome to Orchestrator! 👋"

    def display_mode_guidelines(self, mode: ExecutionMode) -> None:
        """Display mode-specific guidelines in compact format.

        Args:
            mode: Current execution mode
        """
        guidelines = self._get_mode_guidelines(mode)
        color = self.MODE_COLORS.get(mode, "white")

        panel = Panel(
            guidelines,
            title=f"💡 [bold]Mode Guidelines: {mode.value.upper()}[/bold]",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()  # Blank line

    def _get_mode_guidelines(self, mode: ExecutionMode) -> str:
        """Get compact mode guidelines text.

        Args:
            mode: Execution mode

        Returns:
            Guidelines text
        """
        guidelines = {
            ExecutionMode.ASK: """
[bold]ASK Mode[/bold] is for research, exploration, and Q&A.

[green]✓ What you can do:[/green]
  • Ask questions about the codebase
  • Explore files and directories (bash + read-only)
  • Research documentation
  • Get explanations and recommendations

[red]✗ What you cannot do:[/red]
  • Modify files or execute changes
  • Create tasks or subtasks

[dim]Typical use: "What does this function do?", "Show me files in src/"[/dim]
""",
            ExecutionMode.PLAN: """
[bold]PLAN Mode[/bold] is for strategic planning and task decomposition.

[green]✓ What you can do:[/green]
  • Read existing code to understand structure
  • Research best practices (web_fetch)
  • Create task decomposition with dependencies
  • Generate execution checklists

[red]✗ What you cannot do:[/red]
  • Execute changes (file_write, bash execution)
  • Explore filesystem (use ASK mode for exploration)

[dim]Workflow: PLAN creates roadmap → EXECUTE implements it[/dim]
""",
            ExecutionMode.EXECUTE: """
[bold]EXECUTE Mode[/bold] is for full execution with all tools available.

[green]✓ What you can do:[/green]
  • All tools available (file_write, bash, subagents, etc.)
  • Execute pending tasks from PLAN mode
  • Create and execute new tasks directly

[yellow]⚠ What you should avoid:[/yellow]
  • Creating new task decompositions (use PLAN mode first for complex tasks)

[dim]Workflow: Simple tasks → execute directly. Complex → PLAN first, then EXECUTE[/dim]
"""
        }
        return guidelines.get(mode, "").strip()
