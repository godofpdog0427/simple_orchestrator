"""Minimal streaming display manager - pure text output, no Live, no Panel."""

import logging
from typing import Any

from rich.console import Console

from orchestrator.tasks.models import TodoItem

logger = logging.getLogger(__name__)


class StreamingDisplayManager:
    """
    極簡串流輸出 display manager。

    特點:
    - 純文字輸出，無 Panel 框框
    - 無 Live display，無固定區域
    - TODO 只在更新時印一行
    - 內容持續向下滾動
    """

    def __init__(self, console: Console | None = None):
        """
        Initialize minimal streaming display manager.

        Args:
            console: Rich Console instance (creates new if None)
        """
        self.console = console or Console()
        self._enabled = True
        self._current_todos: list[TodoItem] = []
        self._last_todo_output = ""  # Track last TODO line to avoid spam

    def enable(self) -> None:
        """Enable display output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable display output."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if display is enabled."""
        return self._enabled

    # Core append methods (pure text output)

    def update_todo_list(self, todos: list[TodoItem]) -> None:
        """
        只在 TODO 改變時印一行。

        Args:
            todos: List of TODO items
        """
        if not self._enabled or not todos:
            return

        self._current_todos = todos

        # 格式化為單行
        items = []
        for todo in todos[:5]:  # Max 5 items
            icon = {
                "completed": "✅",
                "in_progress": "⏳",
                "pending": "⏸"
            }.get(todo.status, "❓")
            # Truncate long task names
            content = todo.content[:20]
            if len(todo.content) > 20:
                content += "..."
            items.append(f"{icon} {content}")

        output = "TODO: " + "  ".join(items)

        # 只在改變時才印
        if output != self._last_todo_output:
            self.console.print(output, style="dim magenta")
            self._last_todo_output = output

    def append_thinking(self, text: str) -> None:
        """
        印思考文字（純文字，無框框）。

        Args:
            text: Reasoning text from LLM
        """
        if not self._enabled or not text.strip():
            return

        self.console.print(f"💭 {text}", style="cyan")

    def append_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """
        印工具執行開始。

        Args:
            tool_name: Name of the tool
            args: Tool arguments
        """
        if not self._enabled:
            return

        # Format first 2 args
        args_str = ", ".join(
            f"{k}={str(v)[:20]}"
            for k, v in list(args.items())[:2]
        )
        if len(args) > 2:
            args_str += "..."

        self.console.print(f"🔧 {tool_name}({args_str})", style="yellow")

    def append_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """
        印工具執行結果。

        Args:
            tool_name: Name of the tool
            success: Whether execution succeeded
            data: Tool result data
            error: Error message if failed
        """
        if not self._enabled:
            return

        if success:
            result_str = str(data)[:100] if data else "OK"
            if data and len(str(data)) > 100:
                result_str += "..."
            self.console.print(f"  ✅ {result_str}", style="green")
        else:
            self.console.print(f"  ❌ {error or 'Unknown error'}", style="red")

    def append_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """
        印任務開始。

        Args:
            task_title: Task title
            task_description: Optional task description
        """
        if not self._enabled:
            return

        self.console.print(f"\n🚀 Starting Task: {task_title}", style="bold green")
        if task_description and task_description != task_title:
            self.console.print(f"   {task_description}", style="dim")

    def append_task_complete(self, task_title: str, result: str | None = None) -> None:
        """
        印任務完成。

        Args:
            task_title: Task title
            result: Task result
        """
        if not self._enabled:
            return

        self.console.print(f"\n✅ Task Completed: {task_title}", style="bold green")
        if result:
            result_str = str(result)[:200]
            if len(str(result)) > 200:
                result_str += "..."
            self.console.print(f"   {result_str}", style="dim")

    def append_task_failed(self, task_title: str, error: str) -> None:
        """
        印任務失敗。

        Args:
            task_title: Task title
            error: Error message
        """
        if not self._enabled:
            return

        self.console.print(f"\n❌ Task Failed: {task_title}", style="bold red")
        self.console.print(f"   Error: {error}", style="red")

    def append_iteration(self, current: int, maximum: int) -> None:
        """
        印迭代計數。

        Args:
            current: Current iteration
            maximum: Maximum iterations
        """
        if not self._enabled:
            return

        self.console.print(f"[Iteration {current}/{maximum}]", style="dim")

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
        bar_length = 20
        filled = int((current / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        text = f"[{bar}] {percentage}% ({current}/{total})"
        if message:
            text += f" {message}"

        self.console.print(text, style="blue")
