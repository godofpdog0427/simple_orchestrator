"""Unit tests for token estimation utilities."""

from orchestrator.llm.token_utils import (
    estimate_tokens,
    estimate_message_tokens,
    get_context_window,
)


class TestEstimateTokens:
    """Tests for estimate_tokens."""

    def test_empty_string(self):
        assert estimate_tokens("") == 1  # len("") // 4 + 1

    def test_short_string(self):
        assert estimate_tokens("hi") == 1  # len("hi") // 4 + 1

    def test_known_length(self):
        text = "a" * 400
        assert estimate_tokens(text) == 101  # 400 // 4 + 1

    def test_returns_positive(self):
        assert estimate_tokens("x") > 0


class TestEstimateMessageTokens:
    """Tests for estimate_message_tokens."""

    def test_single_text_message(self):
        messages = [{"role": "user", "content": "Hello world"}]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0

    def test_empty_list(self):
        assert estimate_message_tokens([]) == 0

    def test_list_content_with_dict_blocks(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": "result data here"},
                ],
            }
        ]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0

    def test_list_content_with_sdk_objects(self):
        """Non-dict blocks (SDK objects) are stringified."""

        class FakeBlock:
            def __str__(self):
                return "TextBlock(text='hello')"

        messages = [{"role": "assistant", "content": [FakeBlock()]}]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0

    def test_message_overhead(self):
        """Each message adds 4 tokens overhead."""
        one_msg = estimate_message_tokens([{"role": "user", "content": ""}])
        two_msgs = estimate_message_tokens([
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ])
        # Two messages should have ~4 more tokens than one (overhead)
        assert two_msgs - one_msg >= 4

    def test_multiple_messages(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0


class TestGetContextWindow:
    """Tests for get_context_window."""

    def test_known_model(self):
        assert get_context_window("claude-sonnet-4-20250514") == 200_000

    def test_unknown_model_returns_default(self):
        assert get_context_window("unknown-model-xyz") == 200_000

    def test_empty_string_returns_default(self):
        assert get_context_window("") == 200_000
