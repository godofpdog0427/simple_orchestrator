"""Display hook for real-time CLI output."""

import logging
from typing import Any

from orchestrator.display import get_display_manager
from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class DisplayHook(Hook):
    """
    Hook for real-time CLI display of orchestrator execution.

    Monitors events and displays:
    - Task start/completion
    - LLM reasoning (thinking)
    - Tool execution and results
    - TODO list progress
    - Iteration progress
    """

    priority = 5  # Very high priority to display before other hooks

    def __init__(self, config: dict[str, Any]):
        """
        Initialize display hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.show_iterations = config.get("show_iterations", True)
        self.show_reasoning = config.get("show_reasoning", True)
        self.show_tools = config.get("show_tools", True)
        self.show_todos = config.get("show_todos", True)

        self.display = get_display_manager()

    async def execute(self, context: HookContext) -> HookResult:
        """
        Display event information.

        Args:
            context: Hook context

        Returns:
            HookResult to continue execution
        """
        if not self.enabled:
            return HookResult(action="continue")

        try:
            event = context.event
            data = context.data

            # Task lifecycle events
            if event == "task.started":
                self._display_task_start(data)

            elif event == "task.completed":
                self._display_task_complete(data)

            elif event == "task.failed":
                self._display_task_failed(data)

            # LLM events
            elif event == "llm.before_call":
                self._display_iteration(context.metadata)

            elif event == "llm.after_call":
                self._display_reasoning(data)

            # Tool events
            elif event == "tool.before_execute":
                self._display_tool_execution(data)

            elif event == "tool.after_execute":
                self._display_tool_result(data)

        except Exception as e:
            logger.error(f"Error in DisplayHook: {e}", exc_info=True)

        return HookResult(action="continue")

    def _display_task_start(self, data: dict[str, Any]) -> None:
        """Display task start."""
        task = data.get("task")
        if task and hasattr(task, "title"):
            description = getattr(task, "description", None)
            self.display.show_task_start(task.title, description)

    def _display_task_complete(self, data: dict[str, Any]) -> None:
        """Display task completion."""
        task = data.get("task")
        result = data.get("result")

        if task and hasattr(task, "title"):
            self.display.show_task_complete(task.title, result)

    def _display_task_failed(self, data: dict[str, Any]) -> None:
        """Display task failure."""
        task = data.get("task")
        error = data.get("error", "Unknown error")

        if task and hasattr(task, "title"):
            self.display.show_task_failed(task.title, str(error))

    def _display_iteration(self, metadata: dict[str, Any]) -> None:
        """Display reasoning iteration number."""
        if not self.show_iterations:
            return

        current = metadata.get("iteration", 0)
        maximum = metadata.get("max_iterations", 20)

        if current > 0:
            self.display.show_iteration(current, maximum)

    def _display_reasoning(self, data: dict[str, Any]) -> None:
        """Display LLM reasoning text."""
        if not self.show_reasoning:
            return

        # Extract reasoning text from response
        reasoning = data.get("reasoning_text")
        if reasoning:
            self.display.show_thinking(reasoning)

    def _display_tool_execution(self, data: dict[str, Any]) -> None:
        """Display tool execution start."""
        if not self.show_tools:
            return

        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})

        self.display.show_tool_execution(tool_name, tool_input)

    def _display_tool_result(self, data: dict[str, Any]) -> None:
        """Display tool execution result."""
        if not self.show_tools:
            return

        tool_name = data.get("tool_name", "unknown")
        success = data.get("success", False)
        result = data.get("result")

        # Extract data and error from ToolResult
        result_data = None
        error = None

        if result and hasattr(result, "success"):
            result_data = getattr(result, "data", None)
            error = getattr(result, "error", None)

        # Special handling for todo_list tool
        if tool_name == "todo_list" and self.show_todos and success and result_data:
            todos = result_data.get("todos", [])
            if todos:
                # Convert dict todos to TodoItem-like objects for display
                from orchestrator.tasks.models import TodoItem

                todo_items = []
                for todo_dict in todos:
                    if isinstance(todo_dict, dict):
                        todo_items.append(
                            TodoItem(
                                content=todo_dict.get("content", ""),
                                status=todo_dict.get("status", "pending"),
                                active_form=todo_dict.get("active_form", ""),
                            )
                        )
                if todo_items:
                    self.display.show_todo_status(todo_items)
                    return  # Don't show regular tool result for todo_list

        # Show regular tool result
        self.display.show_tool_result(tool_name, success, result_data, error)
