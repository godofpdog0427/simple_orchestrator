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

            # Trigger llm.before_call event
            await self._trigger_hook("llm.before_call", {"messages": messages, "tools": tools})

            # Call LLM with tools
            response = await self.llm_client.chat(messages, tools=tools if tools else None)

            # Trigger llm.after_call event
            token_count = getattr(response, "usage", {}).get("total_tokens", "unknown")
            await self._trigger_hook("llm.after_call", {"response": response, "token_count": token_count})

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
        prompt = """You are an AI assistant helping with task execution.

You have access to tools that will be provided via the API. Use them as needed to complete tasks.

IMPORTANT - Task Progress Tracking:
For complex multi-step tasks, use the 'todo_list' tool to track your progress:
1. Break down the task into clear, actionable steps
2. Use 'write' operation to create your TODO list at the start
3. Mark current step as 'in_progress' when working on it
4. Mark steps as 'completed' when done
5. Use 'list' operation to review progress

This helps you maintain context across reasoning iterations (max 20 iterations).
Without a TODO list, you may lose track of progress in long-running tasks.

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

        # Execute tool
        result = await tool.execute(**tool_args)
        logger.info(f"Tool result: {result.success}")

        # Trigger tool.after_execute event
        await self._trigger_hook(
            "tool.after_execute",
            {"tool_name": tool_name, "tool_input": tool_args, "success": result.success, "result": result},
        )

        return result

    async def _trigger_hook(self, event: str, data: dict[str, Any]) -> Any:
        """
        Trigger a hook event.

        Args:
            event: Event name
            data: Event data

        Returns:
            HookResult
        """
        if not self.hook_engine or not self.hook_engine.is_enabled():
            from orchestrator.hooks.base import HookResult

            return HookResult(action="continue")

        return await self.hook_engine.trigger(event, data, orchestrator_state=self)
