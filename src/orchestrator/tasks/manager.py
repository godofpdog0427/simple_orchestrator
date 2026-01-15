"""Task manager for managing task lifecycle."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from orchestrator.tasks.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager for task creation, storage, and retrieval."""

    def __init__(self, config: dict) -> None:
        """
        Initialize task manager.

        Args:
            config: Task configuration
        """
        self.config = config
        self.tasks: dict[str, Task] = {}
        self.max_pending_tasks = config.get("max_pending_tasks", 100)

    async def create_task(self, task: Task) -> Task:
        """
        Create a new task.

        Args:
            task: Task to create

        Returns:
            Created task
        """
        pending_count = len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        if pending_count >= self.max_pending_tasks:
            raise RuntimeError(
                f"Max pending tasks limit reached ({self.max_pending_tasks})"
            )

        self.tasks[task.id] = task
        logger.info(f"Created task: {task.id} - {task.title}")

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        return self.tasks.get(task_id)

    async def update_task(self, task_id: str, updates: dict) -> Task:
        """
        Update a task.

        Args:
            task_id: Task ID
            updates: Dictionary of fields to update

        Returns:
            Updated task

        Raises:
            KeyError: If task not found
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()

        if task.status == TaskStatus.COMPLETED and not task.completed_at:
            task.completed_at = datetime.utcnow()

        logger.debug(f"Updated task: {task_id}")

        return task

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.

        Args:
            task_id: Task ID

        Returns:
            True if deleted, False if not found
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
        return False

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        parent_id: Optional[str] = None,
    ) -> list[Task]:
        """
        List tasks with optional filters.

        Args:
            status: Filter by status
            parent_id: Filter by parent task ID

        Returns:
            List of tasks
        """
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if parent_id is not None:
            tasks = [t for t in tasks if t.parent_id == parent_id]

        return tasks

    async def get_next_executable_task(self) -> Optional[Task]:
        """
        Get the next task that can be executed.

        For Phase 1 (no hierarchy/dependencies):
        - Just returns the first PENDING task

        Returns:
            Next executable task or None
        """
        pending_tasks = await self.list_tasks(status=TaskStatus.PENDING)

        if not pending_tasks:
            return None

        return pending_tasks[0]

    async def save_state(self, path: Optional[Path] = None) -> None:
        """
        Save task state to file.

        Args:
            path: Optional path to save to, defaults to config
        """
        if path is None:
            persistence_config = self.config.get("persistence", {})
            if not persistence_config.get("enabled", True):
                logger.debug("Persistence disabled, skipping save")
                return

            state_file = persistence_config.get("state_file", "./.orchestrator/state.json")
            path = Path(state_file)

        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "tasks": {
                task_id: task.model_dump(mode="json")
                for task_id, task in self.tasks.items()
            }
        }

        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)

            logger.info(f"Saved task state to {path}")

        except Exception as e:
            logger.error(f"Error saving task state: {e}", exc_info=True)

    async def load_state(self, path: Optional[Path] = None) -> None:
        """
        Load task state from file.

        Args:
            path: Optional path to load from, defaults to config
        """
        if path is None:
            persistence_config = self.config.get("persistence", {})
            if not persistence_config.get("enabled", True):
                logger.debug("Persistence disabled, skipping load")
                return

            state_file = persistence_config.get("state_file", "./.orchestrator/state.json")
            path = Path(state_file)

        if not path.exists():
            logger.debug(f"State file does not exist: {path}")
            return

        try:
            with open(path, "r") as f:
                state = json.load(f)

            if "tasks" in state:
                for task_id, task_data in state["tasks"].items():
                    task = Task(**task_data)
                    self.tasks[task_id] = task

            logger.info(f"Loaded {len(self.tasks)} tasks from {path}")

        except Exception as e:
            logger.error(f"Error loading task state: {e}", exc_info=True)

    async def decompose_task(self, task_id: str, subtasks: list[Task]) -> Task:
        """
        Break down a task into subtasks.

        Note: For Phase 1, this is a placeholder.
        Full implementation in Phase 3 (hierarchical tasks).

        Args:
            task_id: Parent task ID
            subtasks: List of subtask definitions

        Returns:
            Updated parent task
        """
        logger.warning("Task decomposition not implemented in Phase 1")
        task = await self.get_task(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        return task
