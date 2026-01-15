"""Built-in Human-in-the-Loop (HITL) hooks."""

import asyncio
import logging
from typing import Any

from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class HITLHook(Hook):
    """
    Hook that prompts user for approval on critical operations.

    Triggers on: tool.requires_approval event

    Config options:
        timeout: Approval timeout in seconds (default: 300)
        auto_approve_safe_tools: Auto-approve tools with requires_approval=False (default: True)
        prompt_format: Custom prompt format (default: standard)
    """

    priority = 50  # Medium priority, after logging but before metrics

    def __init__(self, config: dict[str, Any]):
        """
        Initialize HITL hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.timeout = config.get("timeout", 300)
        self.auto_approve_safe_tools = config.get("auto_approve_safe_tools", True)
        self.prompt_format = config.get("prompt_format", "standard")

    async def execute(self, context: HookContext) -> HookResult:
        """
        Prompt user for approval.

        Context data should contain:
            - tool_name: str - Name of the tool
            - tool_input: dict - Tool input parameters
            - requires_approval: bool - Whether tool requires approval

        Args:
            context: Hook context

        Returns:
            HookResult: continue if approved, block if denied
        """
        data = context.data
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})
        requires_approval = data.get("requires_approval", False)

        # Auto-approve tools that don't require approval
        if self.auto_approve_safe_tools and not requires_approval:
            logger.debug(f"Auto-approving safe tool: {tool_name}")
            return HookResult(action="continue")

        # Prompt user for approval
        try:
            approved = await self._prompt_user(tool_name, tool_input)

            if approved:
                logger.info(f"User approved tool execution: {tool_name}")
                return HookResult(action="continue")
            else:
                reason = f"User denied approval for tool '{tool_name}'"
                logger.info(reason)
                return HookResult(action="block", reason=reason)

        except asyncio.TimeoutError:
            reason = f"Approval timeout ({self.timeout}s) for tool '{tool_name}'"
            logger.warning(reason)
            return HookResult(action="block", reason=reason)

        except Exception as e:
            reason = f"Error during approval prompt: {e}"
            logger.error(reason, exc_info=True)
            return HookResult(action="block", reason=reason)

    async def _prompt_user(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        """
        Prompt user for approval via console.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            bool: True if approved, False if denied

        Raises:
            asyncio.TimeoutError: If prompt times out
        """
        # Format prompt
        prompt_text = self._format_prompt(tool_name, tool_input)

        # Run prompt in executor to avoid blocking
        loop = asyncio.get_event_loop()

        async def get_input():
            return await loop.run_in_executor(None, input, prompt_text)

        # Wait for user input with timeout
        try:
            response = await asyncio.wait_for(get_input(), timeout=self.timeout)
            return response.strip().lower() in ["y", "yes"]
        except asyncio.TimeoutError:
            print("\n[Timeout - request denied]")
            raise

    def _format_prompt(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Format approval prompt.

        Args:
            tool_name: Tool name
            tool_input: Tool input

        Returns:
            Formatted prompt string
        """
        if self.prompt_format == "detailed":
            lines = [
                "\n" + "=" * 60,
                "APPROVAL REQUIRED",
                "=" * 60,
                f"Tool: {tool_name}",
                "Parameters:",
            ]
            for key, value in tool_input.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                lines.append(f"  {key}: {value_str}")
            lines.append("=" * 60)
            lines.append("Approve? [y/N]: ")
            return "\n".join(lines)

        else:  # standard format
            # Format tool input concisely
            input_str = self._format_input_brief(tool_input)
            return f"\n⚠️  Tool '{tool_name}' requires approval\n   Input: {input_str}\n   Approve? [y/N]: "

    def _format_input_brief(self, tool_input: dict[str, Any]) -> str:
        """
        Format tool input briefly for prompt.

        Args:
            tool_input: Tool input parameters

        Returns:
            Brief formatted string
        """
        if not tool_input:
            return "{}"

        items = []
        for key, value in tool_input.items():
            value_str = str(value)
            # Truncate long values
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            items.append(f"{key}={value_str}")

        return "{" + ", ".join(items) + "}"

    def should_run(self, context: HookContext) -> bool:
        """
        Check if hook should run for this context.

        Only run for tool.requires_approval event.

        Args:
            context: Hook context

        Returns:
            bool: True if should run
        """
        return context.event == "tool.requires_approval"
