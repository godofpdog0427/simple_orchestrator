"""Task summarizer for generating concise LLM-based summaries."""

import logging
from typing import Any

from orchestrator.tasks.models import Task

logger = logging.getLogger(__name__)


class TaskSummarizer:
    """Generates task summaries using LLM."""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    async def generate_summary(
        self, task: Task, task_conversation: list[dict]
    ) -> str:
        """
        Generate 2-3 sentence summary of task execution.

        Args:
            task: The completed task
            task_conversation: List of conversation messages from reasoning loop

        Returns:
            Concise summary string
        """
        # Extract key information
        tools_used = self._extract_tools_used(task_conversation)
        reasoning_text = self._extract_reasoning(task_conversation)

        # Build summary prompt
        summary_prompt = f"""Summarize this task execution in 2-3 sentences.
Focus on what was accomplished, key decisions, and results.

Task: {task.description}
Status: {task.status.value}
Tools Used: {', '.join(tools_used) if tools_used else 'None'}

Reasoning:
{reasoning_text[:1000]}

Summary:"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": summary_prompt}],
            )

            # LLMResponse has .content list of blocks; extract text
            summary = self._extract_text_from_response(response)
            logger.debug(f"Generated summary for task {task.id}: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary for task {task.id}: {e}")
            # Fallback: Return truncated task description
            return f"{task.description[:100]}... (Status: {task.status.value})"

    async def summarize_turns(self, dropped_turns: list[dict]) -> str:
        """
        Generate a concise summary of dropped conversation turns.

        Args:
            dropped_turns: List of conversation messages being dropped

        Returns:
            Summary string of the dropped context
        """
        tools_used = self._extract_tools_used(dropped_turns)
        reasoning_text = self._extract_reasoning(dropped_turns)
        tool_outputs = self._extract_tool_outputs(dropped_turns)

        summary_prompt = f"""Summarize these agent conversation turns in 2-4 sentences.
Focus on tools executed, key findings, and decisions.

Tools used: {', '.join(tools_used) if tools_used else 'None'}

Reasoning:
{reasoning_text[:800]}

Tool outputs (truncated):
{tool_outputs[:800]}

Summary:"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": summary_prompt}],
            )
            return self._extract_text_from_response(response)

        except Exception as e:
            logger.error(f"Error summarizing dropped turns: {e}")
            # Fallback
            if tools_used:
                return f"Earlier conversation used tools: {', '.join(tools_used)}"
            return "Earlier conversation context was dropped."

    def _extract_text_from_response(self, response: Any) -> str:
        """Extract text content from an LLMResponse object."""
        if hasattr(response, "content") and isinstance(response.content, list):
            texts = []
            for block in response.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return " ".join(texts).strip()
        return str(response).strip()

    def _extract_tool_outputs(self, conversation: list[dict]) -> str:
        """Extract tool result content from conversation, truncated."""
        outputs = []
        for msg in conversation:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str) and content:
                            outputs.append(content[:200])
        return "\n".join(outputs)

    def _extract_tools_used(self, conversation: list[dict]) -> list[str]:
        """Extract list of tools used during task execution."""
        tools = set()
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools.add(block.get("name", "unknown"))
                        elif hasattr(block, "type") and block.type == "tool_use":
                            tools.add(getattr(block, "name", "unknown"))
        return list(tools)

    def _extract_reasoning(self, conversation: list[dict]) -> str:
        """Extract text reasoning blocks from conversation."""
        reasoning = []
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            reasoning.append(block.get("text", ""))
                elif isinstance(content, str):
                    reasoning.append(content)
        return "\n".join(reasoning)
