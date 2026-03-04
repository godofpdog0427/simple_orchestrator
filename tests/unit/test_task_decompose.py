"""Unit tests for TaskDecomposeTool structured error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from orchestrator.tools.builtin.task_decompose import TaskDecomposeTool
from orchestrator.tasks.models import Task, TaskStatus, TaskPriority


class TestTaskDecomposeErrorHandling:
    """Tests for structured error messages in add/remove dependency."""

    @pytest.fixture
    def tool(self):
        """TaskDecomposeTool with mocked task_manager and current_task."""
        t = TaskDecomposeTool()
        t.task_manager = AsyncMock()
        t.current_task = MagicMock(spec=Task)
        t.current_task.id = "current-task-id"
        return t

    # --- add_dependency: circular dependency ---

    @pytest.mark.asyncio
    async def test_add_dependency_circular_returns_structured_error(self, tool):
        tool.task_manager.add_dependency.side_effect = ValueError(
            "Adding dependency task_a -> task_b would create a cycle"
        )

        result = await tool.execute(
            operation="add_dependency",
            depends_on_task_id="task_b",
        )

        assert result.success is False
        assert "Circular dependency detected" in result.error
        assert "get_task_info" in result.error

    # --- add_dependency: self-dependency ---

    @pytest.mark.asyncio
    async def test_add_dependency_self_returns_structured_error(self, tool):
        tool.task_manager.add_dependency.side_effect = ValueError(
            "Task cannot depend on itself"
        )

        result = await tool.execute(
            operation="add_dependency",
            task_id="task_a",
            depends_on_task_id="task_a",
        )

        assert result.success is False
        assert "Self-dependency not allowed" in result.error

    # --- add_dependency: task not found ---

    @pytest.mark.asyncio
    async def test_add_dependency_task_not_found_returns_structured_error(self, tool):
        tool.task_manager.add_dependency.side_effect = KeyError(
            "Task not found: nonexistent-id"
        )

        result = await tool.execute(
            operation="add_dependency",
            depends_on_task_id="nonexistent-id",
        )

        assert result.success is False
        assert "Task not found" in result.error
        assert "list_subtasks" in result.error

    # --- add_dependency: unknown ValueError (fallback) ---

    @pytest.mark.asyncio
    async def test_add_dependency_unknown_value_error_passes_through(self, tool):
        tool.task_manager.add_dependency.side_effect = ValueError(
            "Some unexpected validation error"
        )

        result = await tool.execute(
            operation="add_dependency",
            depends_on_task_id="task_b",
        )

        assert result.success is False
        assert "Some unexpected validation error" in result.error

    # --- remove_dependency: task not found ---

    @pytest.mark.asyncio
    async def test_remove_dependency_task_not_found_returns_structured_error(self, tool):
        tool.task_manager.remove_dependency.side_effect = KeyError(
            "Task not found: nonexistent-id"
        )

        result = await tool.execute(
            operation="remove_dependency",
            depends_on_task_id="nonexistent-id",
        )

        assert result.success is False
        assert "Task not found" in result.error
        assert "list_subtasks" in result.error

    # --- happy paths (regression) ---

    @pytest.mark.asyncio
    async def test_add_dependency_success(self, tool):
        tool.task_manager.add_dependency = AsyncMock()

        result = await tool.execute(
            operation="add_dependency",
            depends_on_task_id="dep-task-id",
        )

        assert result.success is True
        assert result.data["depends_on"] == "dep-task-id"
        tool.task_manager.add_dependency.assert_awaited_once_with(
            "current-task-id", "dep-task-id"
        )

    @pytest.mark.asyncio
    async def test_remove_dependency_success(self, tool):
        tool.task_manager.remove_dependency = AsyncMock()

        result = await tool.execute(
            operation="remove_dependency",
            depends_on_task_id="dep-task-id",
        )

        assert result.success is True
        assert result.data["removed_dependency"] == "dep-task-id"
        tool.task_manager.remove_dependency.assert_awaited_once_with(
            "current-task-id", "dep-task-id"
        )
