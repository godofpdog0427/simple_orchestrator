"""Streaming display manager with fixed TODO at top (Claude Code-like)."""

import asyncio
import logging
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from orchestrator.tasks.models import TodoItem

logger = logging.getLogger(__name__)


class StreamingDisplayManager:
    """
    Display manager with Claude Code-like behavior:
    - Top: Fixed TODO panel (Live updates)
    - Middle: Streaming output (Rich console prints, natural scroll)
    - Bottom: Input prompt (handled by CLI)

    Design:
    - TODO zone uses Rich Live for in-place updates
    - Output directly prints to console (append-only, no replacement)
    - Compact single-line TODO format (max 5 items visible)
    """

    def __init__(self, console: Console | None = None):
        """
        Initialize streaming display manager.

        Args:
            console: Rich Console instance (creates new if None)
        """
        self.console = console or Console()
        self._is_streaming = False
        self._enabled = True

        # TODO zone state (top, fixed)
        self._current_todos: list[TodoItem] = []
        self._todo_live: Optional[Live] = None

    def enable(self) -> None:
        """Enable display output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable display output."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if display is enabled."""
        return self._enabled

    def start_streaming(self) -> None:
        """Start streaming mode with live TODO zone at top."""
        if self._is_streaming:
            return

        self._is_streaming = True
        self._start_todo_live_display()
        logger.info("Streaming display started")

    def stop_streaming(self) -> None:
        """Stop streaming mode and clean up."""
        if not self._is_streaming:
            return

        self._is_streaming = False
        self._stop_todo_live_display()
        logger.info("Streaming display stopped")

    def _start_todo_live_display(self) -> None:
        """Start Live display for TODO zone at top of terminal."""
        if self._todo_live:
            return  # Already started

        try:
            self._todo_live = Live(
                self._render_todo_panel(),
                console=self.console,
                refresh_per_second=4,
                vertical_overflow="visible",  # Allow content below to scroll
                transient=False,  # Keep TODO visible
            )
            self._todo_live.start()
        except Exception as e:
            logger.error(f"Failed to start TODO live display: {e}")
            self._todo_live = None

    def _stop_todo_live_display(self) -> None:
        """Stop Live display for TODO zone."""
        if self._todo_live:
            try:
                self._todo_live.stop()
            except Exception as e:
                logger.error(f"Failed to stop TODO live display: {e}")
            finally:
                self._todo_live = None

    def _render_todo_panel(self) -> Panel:
        """
        Render TODO list as compact panel for live display.

        Returns:
            Panel with TODO items in single-line format
        """
        if not self._current_todos:
            return Panel(
                Text("No active tasks", style="dim"),
                title="📋 TODO Progress",
                border_style="magenta",
                height=3,
            )

        # Compact single-line format for TODO items (max 5 items)
        todo_text = Text()
        for i, todo in enumerate(self._current_todos[:5]):
            if i > 0:
                todo_text.append("  ")

            # Status icon and styling
            icon = self._get_status_icon(todo.status)
            style = self._get_status_style(todo.status)

            todo_text.append(f"{icon} ", style=style)

            # Truncate long task names to 30 chars
            content = todo.content[:30]
            if len(todo.content) > 30:
                content += "..."
            todo_text.append(content, style="cyan")

        # Show count if more than 5 items
        if len(self._current_todos) > 5:
            todo_text.append(f"  [dim](+{len(self._current_todos) - 5} more)[/dim]")

        return Panel(
            todo_text,
            title="📋 TODO Progress",
            border_style="magenta",
            height=3,
        )

    def _get_status_icon(self, status: str) -> str:
        """Get icon for TODO status."""
        return {
            "completed": "✅",
            "in_progress": "⏳",
            "pending": "⏸",
        }.get(status, "❓")

    def _get_status_style(self, status: str) -> str:
        """Get Rich style for TODO status."""
        return {
            "completed": "green",
            "in_progress": "yellow",
            "pending": "dim",
        }.get(status, "white")

    def update_todo_list(self, todos: list[TodoItem]) -> None:
        """
        Update TODO zone (live update at top).

        Args:
            todos: List of TODO items
        """
        if not self._enabled:
            return

        self._current_todos = todos

        # Update live display if active
        if self._todo_live:
            try:
                self._todo_live.update(self._render_todo_panel())
            except Exception as e:
                logger.error(f"Failed to update TODO display: {e}")

    # Append-only methods (print directly to console, below TODO zone)

    def append_iteration(self, current: int, maximum: int) -> None:
        """
        Print iteration counter.

        Args:
            current: Current iteration
            maximum: Maximum iterations
        """
        if not self._enabled:
            return

        text = Text(f"── Iteration {current}/{maximum} ──", style="dim yellow")
        self.console.print(text)

    def append_thinking(self, text: str) -> None:
        """
        Print thinking text in panel.

        Args:
            text: Reasoning text from LLM
        """
        if not self._enabled or not text.strip():
            return

        panel = Panel(
            Text(text, style="cyan"),
            title="🤔 Thinking",
            border_style="dim cyan",
            padding=(0, 1),
        )
        self.console.print(panel)

    def append_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """
        Print tool execution start.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
        """
        if not self._enabled:
            return

        args_str = self._format_args(args)
        text = Text()
        text.append("🔧 Tool: ", style="yellow")
        text.append(tool_name, style="bold yellow")
        if args_str:
            text.append(f" ({args_str})", style="dim yellow")
        self.console.print(text)

    def append_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """
        Print tool execution result.

        Args:
            tool_name: Name of the tool
            success: Whether execution succeeded
            data: Tool result data
            error: Error message if failed
        """
        if not self._enabled:
            return

        if success:
            title = f"✅ {tool_name} - Success"
            border_style = "green"
            content = str(data)[:500] if data else "[dim]No output[/dim]"
            if data and len(str(data)) > 500:
                content += "..."
        else:
            title = f"❌ {tool_name} - Failed"
            border_style = "red"
            content = error or "Unknown error"

        panel = Panel(
            content,
            title=title,
            border_style=border_style,
            padding=(0, 1),
        )
        self.console.print(panel)

    def append_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """
        Print task start.

        Args:
            task_title: Task title
            task_description: Optional task description
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]"
        if task_description and task_description != task_title:
            content += f"\n{task_description}"

        panel = Panel(
            content,
            title="🚀 Starting Task",
            border_style="green",
        )
        self.console.print(panel)

    def append_task_complete(self, task_title: str, result: str | None = None) -> None:
        """
        Print task completion.

        Args:
            task_title: Task title
            result: Task result
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]"
        if result:
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:497] + "..."
            content += f"\n\n{result_str}"

        panel = Panel(
            content,
            title="✅ Task Completed",
            border_style="green",
        )
        self.console.print(panel)

    def append_task_failed(self, task_title: str, error: str) -> None:
        """
        Print task failure.

        Args:
            task_title: Task title
            error: Error message
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]\n\n[red]Error: {error}[/red]"

        panel = Panel(
            content,
            title="❌ Task Failed",
            border_style="red",
        )
        self.console.print(panel)

    def _format_args(self, args: dict[str, Any]) -> str:
        """
        Format tool arguments for compact display.

        Args:
            args: Tool arguments

        Returns:
            Formatted string (truncated if too long)
        """
        if not args:
            return ""

        # Format as key=value pairs
        parts = []
        for key, value in args.items():
            value_str = str(value)
            # Truncate very long values
            if len(value_str) > 40:
                value_str = value_str[:37] + "..."
            parts.append(f"{key}={value_str}")

        result = ", ".join(parts)
        # Truncate entire args string if too long
        if len(result) > 100:
            result = result[:97] + "..."
        return result

    # Backward compatibility with DisplayManager interface

    def show_thinking(self, text: str) -> None:
        """Alias for append_thinking (backward compatibility)."""
        self.append_thinking(text)

    def show_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """Alias for append_tool_execution (backward compatibility)."""
        self.append_tool_execution(tool_name, args)

    def show_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """Alias for append_tool_result (backward compatibility)."""
        self.append_tool_result(tool_name, success, data, error)

    def show_todo_status(self, todos: list[TodoItem]) -> None:
        """Alias for update_todo_list (backward compatibility)."""
        self.update_todo_list(todos)

    def show_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """Alias for append_task_start (backward compatibility)."""
        self.append_task_start(task_title, task_description)

    def show_task_complete(self, task_title: str, result: str | None = None) -> None:
        """Alias for append_task_complete (backward compatibility)."""
        self.append_task_complete(task_title, result)

    def show_task_failed(self, task_title: str, error: str) -> None:
        """Alias for append_task_failed (backward compatibility)."""
        self.append_task_failed(task_title, error)

    def show_iteration(self, current: int, maximum: int) -> None:
        """Alias for append_iteration (backward compatibility)."""
        self.append_iteration(current, maximum)

    def show_progress(self, current: int, total: int, message: str = "") -> None:
        """
        Display progress indicator.

        Args:
            current: Current step
            total: Total steps
            message: Optional progress message
        """
        if not self._enabled:
            return

        percentage = int((current / total) * 100) if total > 0 else 0
        bar_length = 30
        filled = int((current / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        text = f"Progress: [{bar}] {percentage}% ({current}/{total})"
        if message:
            text += f"\n{message}"

        self.console.print(f"[bold blue]{text}[/bold blue]")
