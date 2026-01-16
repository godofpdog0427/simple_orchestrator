"""Core orchestrator implementation."""

import logging
from typing import Any, Optional

from orchestrator.tasks.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestrator class for managing tasks and LLM interactions."""

    def __init__(self, config: dict) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.should_stop = False
        self.current_task: Optional[Task] = None

        # Components will be initialized in initialize()
        self.llm_client: Optional[Any] = None
        self.tool_registry: Optional[Any] = None
        self.task_manager: Optional[Any] = None
        self.hook_engine: Optional[Any] = None

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup logging based on configuration."""
        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_file = log_config.get("file", "./.orchestrator/logs/orchestrator.log")

        # Configure logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if log_config.get("console", True) else logging.NullHandler(),
            ],
        )

    async def initialize(self) -> None:
        """Initialize orchestrator components."""
        logger.info("Initializing orchestrator...")

        # Import here to avoid circular imports
        from orchestrator.hooks.engine import HookEngine
        from orchestrator.llm.client import LLMClient
        from orchestrator.tasks.manager import TaskManager
        from orchestrator.tools.registry import ToolRegistry

        # Initialize hook engine first
        hook_config = self.config.get("hooks", {})
        self.hook_engine = HookEngine(hook_config)
        await self.hook_engine.initialize()

        # Trigger orchestrator.start event
        await self._trigger_hook("orchestrator.start", {"config": self.config})

        # Initialize LLM client
        llm_config = self.config.get("llm", {})
        self.llm_client = LLMClient(llm_config)

        # Initialize tool registry
        tool_config = self.config.get("tools", {})
        self.tool_registry = ToolRegistry(tool_config)
        await self.tool_registry.initialize()

        # Initialize task manager
        task_config = self.config.get("tasks", {})
        self.task_manager = TaskManager(task_config)

        logger.info("Orchestrator initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown orchestrator and cleanup resources."""
        logger.info("Shutting down orchestrator...")
        self.should_stop = True

        # Trigger orchestrator.stop event
        await self._trigger_hook("orchestrator.stop", {"final_state": {"should_stop": self.should_stop}})

        # Cleanup components
        if self.task_manager:
            await self.task_manager.save_state()

        logger.info("Orchestrator shutdown complete")

    async def run(self) -> None:
        """
        Main orchestrator execution loop.

        This is the core loop that:
        1. Gets next task
        2. Executes task
        3. Repeats until stopped
        """
        await self.initialize()

        try:
            while not self.should_stop:
                # Get next executable task
                task = await self.task_manager.get_next_executable_task()

                if not task:
                    logger.debug("No executable tasks, waiting...")
                    break

                # Execute task
                await self._execute_task(task)

        except Exception as e:
            logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def process_input(self, user_input: str) -> str:
        """
        Process user input in interactive mode.

        Args:
            user_input: User's input string

        Returns:
            Response string
        """
        try:
            # Create task from user input
            task = Task(
                title=user_input[:100],  # Truncate long inputs for title
                description=user_input,
                status=TaskStatus.PENDING,
            )

            # Add task to manager
            task = await self.task_manager.create_task(task)
            logger.info(f"Created task: {task.id}")

            # Execute task
            await self._execute_task(task)

            # Get result
            updated_task = await self.task_manager.get_task(task.id)

            if updated_task and updated_task.status == TaskStatus.COMPLETED:
                return updated_task.result or "Task completed successfully"
            elif updated_task and updated_task.status == TaskStatus.FAILED:
                return f"Task failed: {updated_task.error}"
            else:
                return "Task status unknown"

        except Exception as e:
            logger.error(f"Error processing input: {e}", exc_info=True)
            return f"Error: {e}"

    async def _execute_task(self, task: Task) -> None:
        """
        Execute a single task.

        Args:
            task: Task to execute
        """
        logger.info(f"Executing task: {task.id} - {task.title}")

        try:
            # Update task status
            await self.task_manager.update_task(task.id, {"status": TaskStatus.IN_PROGRESS})
            self.current_task = task

            # Trigger task.started event
            hook_result = await self._trigger_hook("task.started", {"task": task})
            if hook_result.action == "block":
                raise RuntimeError(f"Task blocked by hook: {hook_result.reason}")

            # Build context for LLM
            context = self._build_context(task)

            # Execute reasoning loop
            result = await self._reasoning_loop(task, context)

            # Update task with result
            await self.task_manager.update_task(
                task.id, {"status": TaskStatus.COMPLETED, "result": result}
            )

            # Trigger task.completed event
            await self._trigger_hook("task.completed", {"task": task, "result": result})

            # Phase 3: Handle task completion for dependencies and hierarchy
            await self._handle_task_completion(task.id)

            logger.info(f"Task completed: {task.id}")

        except Exception as e:
            logger.error(f"Task failed: {task.id} - {e}", exc_info=True)
            await self.task_manager.update_task(
                task.id, {"status": TaskStatus.FAILED, "error": str(e)}
            )

            # Trigger task.failed event
            await self._trigger_hook("task.failed", {"task": task, "error": str(e)})

            raise

    def _build_context(self, task: Task) -> dict[str, Any]:
        """
        Build context for LLM based on task.

        Args:
            task: Task to build context for

        Returns:
            Context dictionary
        """
        context = {
            "task": task,
            "tools": self.tool_registry.get_tool_schemas() if self.tool_registry else [],
            "conversation_history": [],
        }

        return context

    async def _reasoning_loop(self, task: Task, context: dict[str, Any]) -> Any:
        """
        Core LLM reasoning loop using Anthropic's native tool calling.

        Args:
            task: Current task
            context: Execution context

        Returns:
            Task result
        """
        max_iterations = self.config.get("orchestrator", {}).get("max_iterations", 20)
        conversation_history = []

        for iteration in range(max_iterations):
            logger.debug(f"Reasoning iteration {iteration + 1}/{max_iterations}")

            # Prepare messages for LLM
            messages = self._prepare_messages(task, context, conversation_history)

            # Get tool schemas for API
            tools = context.get("tools", [])

            # Trigger llm.before_call event with iteration metadata
            await self._trigger_hook(
                "llm.before_call",
                {"messages": messages, "tools": tools},
                metadata={"iteration": iteration + 1, "max_iterations": max_iterations},
            )

            # Call LLM with tools
            response = await self.llm_client.chat(messages, tools=tools if tools else None)

            # Extract reasoning text from response
            reasoning_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    reasoning_text += block.text + "\n"

            # Trigger llm.after_call event with reasoning text
            token_count = getattr(response, "usage", {}).get("total_tokens", "unknown")
            await self._trigger_hook(
                "llm.after_call",
                {"response": response, "token_count": token_count, "reasoning_text": reasoning_text.strip()},
            )

            # Process response based on stop_reason
            if response.stop_reason == "end_turn":
                # Extract text content from response
                text_content = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "text":
                        text_content.append(block.text)

                result = "\n".join(text_content) if text_content else "Task completed"
                return result

            elif response.stop_reason == "tool_use":
                # Add assistant message with tool_use blocks to history
                conversation_history.append({"role": "assistant", "content": response.content})

                # Process each tool use
                tool_results = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        logger.info(f"Executing tool: {block.name}")

                        # Execute tool
                        tool_result = await self._execute_tool(block.name, block.input)

                        # Build tool result in Anthropic format
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(tool_result.data if tool_result.success else tool_result.error),
                            }
                        )

                # Add tool results as user message
                conversation_history.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "max_tokens":
                logger.warning("Response hit max_tokens limit")
                # Continue loop to get more output

            else:
                logger.warning(f"Unknown stop_reason: {response.stop_reason}")

        raise RuntimeError(f"Task {task.id} exceeded max iterations ({max_iterations})")

    def _prepare_messages(
        self, task: Task, context: dict[str, Any], conversation_history: list[dict]
    ) -> list[dict]:
        """
        Prepare messages for LLM.

        Args:
            task: Current task
            context: Context dictionary
            conversation_history: Previous conversation

        Returns:
            List of messages
        """
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(context),
            },
            {
                "role": "user",
                "content": f"Task: {task.description or task.title}",
            },
        ]

        # Add conversation history
        messages.extend(conversation_history)

        return messages

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        """
        Build system prompt for LLM.

        Args:
            context: Context dictionary

        Returns:
            System prompt string
        """
        # For Anthropic, tools are passed via API parameter, not in system prompt
        max_iterations = self.config.get("orchestrator", {}).get("max_iterations", 20)
        prompt = f"""You are an AI assistant helping with task execution.

You have access to tools that will be provided via the API. Use them as needed to complete tasks.

IMPORTANT - Task Progress Tracking:
For complex multi-step tasks, use the 'todo_list' tool to track your progress:
1. Break down the task into clear, actionable steps
2. Use 'write' operation to create your TODO list at the start
3. Mark current step as 'in_progress' when working on it
4. Mark steps as 'completed' when done
5. Use 'list' operation to review progress

This helps you maintain context across reasoning iterations (max {max_iterations} iterations).
Without a TODO list, you may lose track of progress in long-running tasks.

IMPORTANT - Task Decomposition:
For very complex multi-step tasks that require structured execution order, use the 'task_decompose' tool:
1. Analyze the task and identify logical subtasks
2. Use 'create_subtask' operation to break down the work
3. Use 'add_dependency' to set execution order between subtasks (optional)
4. Subtasks will execute automatically before the parent task completes

Example - Create subtask:
{{
  "operation": "create_subtask",
  "title": "Design database schema",
  "description": "Design tables and relationships for user management",
  "priority": "high"
}}

Example - Add dependency (subtask B depends on subtask A):
{{
  "operation": "add_dependency",
  "task_id": "subtask_b_id",
  "depends_on_task_id": "subtask_a_id"
}}

Example - List all subtasks:
{{
  "operation": "list_subtasks"
}}

When to use task_decompose vs todo_list:
- Use 'task_decompose' when subtasks need to be tracked separately, have dependencies, or could fail independently
- Use 'todo_list' for tracking progress within a single task execution

When the task is complete, provide a clear summary of what was accomplished.

If you need more information from the user, ask clearly and specifically."""

        return prompt

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> Any:
        """
        Execute a tool with hook support for HITL.

        Args:
            tool_name: Name of tool to execute
            tool_args: Tool arguments

        Returns:
            Tool result
        """
        logger.info(f"Executing tool: {tool_name}")

        tool = self.tool_registry.get(tool_name)
        if not tool:
            from orchestrator.tools.base import ToolResult

            return ToolResult(success=False, error=f"Tool not found: {tool_name}")

        # Check if tool requires approval
        requires_approval = tool.definition.requires_approval

        # Trigger tool.before_execute event
        hook_result = await self._trigger_hook(
            "tool.before_execute",
            {"tool_name": tool_name, "tool_input": tool_args, "requires_approval": requires_approval},
        )

        if hook_result.action == "block":
            from orchestrator.tools.base import ToolResult

            reason = hook_result.reason or "Tool execution blocked by hook"
            logger.warning(f"Tool {tool_name} blocked: {reason}")
            return ToolResult(success=False, error=reason)

        # Trigger HITL approval if needed
        if requires_approval:
            approval_result = await self._trigger_hook(
                "tool.requires_approval",
                {"tool_name": tool_name, "tool_input": tool_args, "requires_approval": True},
            )

            if approval_result.action == "block":
                from orchestrator.tools.base import ToolResult

                reason = approval_result.reason or "Tool execution denied by user"
                logger.warning(f"Tool {tool_name} denied: {reason}")
                return ToolResult(success=False, error=reason)

        # Inject current task into TodoListTool if applicable
        if tool_name == "todo_list" and hasattr(tool, "set_current_task"):
            tool.set_current_task(self.current_task)

        # Inject current task and task manager into TaskDecomposeTool (Phase 3)
        if tool_name == "task_decompose":
            if hasattr(tool, "set_current_task"):
                tool.set_current_task(self.current_task)
            if hasattr(tool, "set_task_manager"):
                tool.set_task_manager(self.task_manager)

        # Execute tool
        result = await tool.execute(**tool_args)
        logger.info(f"Tool result: {result.success}")

        # Trigger tool.after_execute event
        await self._trigger_hook(
            "tool.after_execute",
            {"tool_name": tool_name, "tool_input": tool_args, "success": result.success, "result": result},
        )

        return result

    async def _trigger_hook(self, event: str, data: dict[str, Any], metadata: dict[str, Any] | None = None) -> Any:
        """
        Trigger a hook event.

        Args:
            event: Event name
            data: Event data
            metadata: Optional metadata to pass to hooks

        Returns:
            HookResult
        """
        if not self.hook_engine or not self.hook_engine.is_enabled():
            from orchestrator.hooks.base import HookResult

            return HookResult(action="continue")

        return await self.hook_engine.trigger(event, data, orchestrator_state=self, metadata=metadata)

    async def _handle_task_completion(self, completed_task_id: str) -> None:
        """
        Handle task completion for Phase 3 hierarchy and dependencies.

        After a task completes:
        1. Unblock tasks that were waiting on this task
        2. Check if parent task can be marked as completed

        Args:
            completed_task_id: ID of the task that just completed
        """
        # Unblock dependent tasks
        await self._unblock_dependent_tasks(completed_task_id)

        # Check parent completion
        completed_task = await self.task_manager.get_task(completed_task_id)
        if completed_task and completed_task.parent_id:
            await self._check_parent_completion(completed_task.parent_id)

    async def _unblock_dependent_tasks(self, completed_task_id: str) -> None:
        """
        Check and unblock tasks that were waiting on the completed task.

        Args:
            completed_task_id: ID of the completed task
        """
        completed_task = await self.task_manager.get_task(completed_task_id)
        if not completed_task:
            return

        # Get all tasks blocked by this task
        for blocked_task_id in completed_task.blocks:
            blocked_task = await self.task_manager.get_task(blocked_task_id)
            if not blocked_task or blocked_task.status != TaskStatus.BLOCKED:
                continue

            # Check if all dependencies are now completed
            all_deps_completed = True
            for dep_id in blocked_task.depends_on:
                dep_task = await self.task_manager.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_deps_completed = False
                    break

            # Unblock task if all dependencies are satisfied
            if all_deps_completed:
                await self.task_manager.update_task(
                    blocked_task_id, {"status": TaskStatus.PENDING}
                )
                logger.info(
                    f"Unblocked task {blocked_task_id} (all dependencies completed)"
                )

    async def _check_parent_completion(self, parent_id: str) -> None:
        """
        Check if parent task can be marked as completed.

        A parent task is automatically completed if all its subtasks are completed.

        Args:
            parent_id: ID of the parent task to check
        """
        parent = await self.task_manager.get_task(parent_id)
        if not parent:
            return

        # Only auto-complete if parent is IN_PROGRESS
        if parent.status != TaskStatus.IN_PROGRESS:
            return

        # Check if all subtasks are completed
        all_subtasks_completed = True
        for subtask_id in parent.subtasks:
            subtask = await self.task_manager.get_task(subtask_id)
            if not subtask or subtask.status != TaskStatus.COMPLETED:
                all_subtasks_completed = False
                break

        # Auto-complete parent if all subtasks are done
        if all_subtasks_completed and parent.subtasks:
            await self.task_manager.update_task(
                parent_id,
                {
                    "status": TaskStatus.COMPLETED,
                    "result": f"All {len(parent.subtasks)} subtasks completed successfully",
                },
            )
            logger.info(f"Auto-completed parent task {parent_id} (all subtasks done)")

            # Trigger completion event
            await self._trigger_hook(
                "task.completed",
                {"task": parent, "result": "All subtasks completed"},
            )

            # Recursively check grandparent
            if parent.parent_id:
                await self._check_parent_completion(parent.parent_id)
