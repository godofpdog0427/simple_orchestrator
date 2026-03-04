"""Unit tests for connection error handling and retry logic."""

import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.llm.client import AnthropicProvider


class FakeAPIConnectionError(Exception):
    """Simulates anthropic.APIConnectionError."""
    pass


# Give it the class name that _is_connection_error checks
FakeAPIConnectionError.__name__ = "APIConnectionError"


class FakeRateLimitError(Exception):
    """Simulates anthropic.RateLimitError."""
    pass


FakeRateLimitError.__name__ = "RateLimitError"


@pytest.fixture
def provider():
    """Create an AnthropicProvider with mocked client and fast retry settings."""
    config = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 100,
        "temperature": 0.7,
    }
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("anthropic.AsyncAnthropic"):
        p = AnthropicProvider(config)
    # Speed up retries for tests
    p.base_delay = 0.01
    p.max_delay = 0.05
    p.max_retries = 2
    return p


class TestIsConnectionError:
    """Tests for _is_connection_error helper."""

    def test_detects_api_connection_error_by_class_name(self, provider):
        err = FakeAPIConnectionError("Connection error.")
        assert provider._is_connection_error(err) is True

    def test_detects_connection_keyword_in_message(self, provider):
        err = Exception("Connection refused by server")
        assert provider._is_connection_error(err) is True

    def test_detects_timeout_keyword_in_message(self, provider):
        err = Exception("Request timeout after 30s")
        assert provider._is_connection_error(err) is True

    def test_rejects_unrelated_error(self, provider):
        err = ValueError("Invalid parameter")
        assert provider._is_connection_error(err) is False

    def test_does_not_false_positive_on_rate_limit(self, provider):
        err = FakeRateLimitError("429 Too Many Requests")
        assert provider._is_connection_error(err) is False


class TestChatRetryOnConnectionError:
    """Tests for chat() retrying on connection errors."""

    @pytest.mark.asyncio
    async def test_chat_retries_on_connection_error_then_succeeds(self, provider):
        """Connection error on first attempt, success on second."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.model = "claude-sonnet-4-20250514"

        provider.client.messages.create = AsyncMock(
            side_effect=[FakeAPIConnectionError("Connection error."), mock_response]
        )

        result = await provider.chat([{"role": "user", "content": "hi"}])
        assert result is not None
        assert provider.client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_raises_after_max_retries(self, provider):
        """Connection error persists through all retries."""
        provider.client.messages.create = AsyncMock(
            side_effect=FakeAPIConnectionError("Connection error.")
        )

        with pytest.raises(FakeAPIConnectionError):
            await provider.chat([{"role": "user", "content": "hi"}])

        # max_retries=2, so 3 total attempts
        assert provider.client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_chat_does_not_retry_unrelated_error(self, provider):
        """Non-connection, non-rate-limit errors are not retried."""
        provider.client.messages.create = AsyncMock(
            side_effect=ValueError("Bad input")
        )

        with pytest.raises(ValueError):
            await provider.chat([{"role": "user", "content": "hi"}])

        assert provider.client.messages.create.call_count == 1


class TestChatStreamRetryOnConnectionError:
    """Tests for chat_stream() retrying on connection errors."""

    @pytest.mark.asyncio
    async def test_stream_retries_on_connection_error_before_yield(self, provider):
        """Connection error before any chunks yielded triggers retry."""
        # First call raises, second call succeeds
        call_count = 0

        class MockStreamContext:
            async def __aenter__(self_inner):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise FakeAPIConnectionError("Connection error.")
                return self_inner

            async def __aexit__(self_inner, *args):
                pass

            @property
            def text_stream(self_inner):
                return self_inner._text_stream()

            async def _text_stream(self_inner):
                yield "Hello"

            async def get_final_message(self_inner):
                msg = MagicMock()
                msg.content = [MagicMock(type="text", text="Hello")]
                msg.stop_reason = "end_turn"
                msg.usage.input_tokens = 10
                msg.usage.output_tokens = 5
                msg.model = "claude-sonnet-4-20250514"
                return msg

        provider.client.messages.stream = MagicMock(return_value=MockStreamContext())

        chunks = []
        async for item in provider.chat_stream([{"role": "user", "content": "hi"}]):
            chunks.append(item)

        assert call_count == 2  # One failure + one success
        assert len(chunks) >= 1  # At least the text chunk

    @pytest.mark.asyncio
    async def test_stream_does_not_retry_unrelated_error(self, provider):
        """Non-connection errors are not retried in streaming."""

        class MockStreamContext:
            async def __aenter__(self_inner):
                raise ValueError("Bad input")

            async def __aexit__(self_inner, *args):
                pass

        provider.client.messages.stream = MagicMock(return_value=MockStreamContext())

        with pytest.raises(ValueError):
            async for _ in provider.chat_stream([{"role": "user", "content": "hi"}]):
                pass
