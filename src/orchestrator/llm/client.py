"""LLM client abstraction."""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: list[Any]  # Content blocks (text or tool_use)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", etc.
    usage: dict[str, int]  # Token usage stats
    model: str
    raw_response: Any  # Original response object


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None
    ) -> LLMResponse:
        """
        Send chat request to LLM.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions

        Returns:
            LLMResponse object
        """
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: dict) -> None:
        """
        Initialize Anthropic provider.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)

        # Get API key
        api_key_env = config.get("api_key_env", "ANTHROPIC_API_KEY")
        self.api_key = os.getenv(api_key_env)

        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Initialize Anthropic client
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

        logger.info(f"Initialized Anthropic provider with model: {self.model}")

    async def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None
    ) -> LLMResponse:
        """
        Send chat request to Anthropic API.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions in Anthropic format

        Returns:
            LLMResponse object
        """
        # Separate system message from conversation
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                conversation_messages.append(msg)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": conversation_messages,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            params["tools"] = tools

        logger.debug(f"Calling Anthropic API with {len(conversation_messages)} messages")

        try:
            response = await self.client.messages.create(**params)

            # Convert to LLMResponse
            return LLMResponse(
                content=response.content,
                stop_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                model=response.model,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise


class LLMClient:
    """Main LLM client that routes to appropriate provider."""

    def __init__(self, config: dict) -> None:
        """
        Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        provider_name = config.get("provider", "anthropic")

        # Initialize provider
        if provider_name == "anthropic":
            provider_config = config.get("anthropic", {})
            self.provider: LLMProvider = AnthropicProvider(provider_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

        logger.info(f"Initialized LLM client with provider: {provider_name}")

    async def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None
    ) -> LLMResponse:
        """
        Send chat request to LLM provider.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions

        Returns:
            LLMResponse object
        """
        return await self.provider.chat(messages, tools)
