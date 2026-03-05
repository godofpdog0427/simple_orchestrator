"""Unit tests for context window management (Observation Masking)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_orchestrator(config_overrides=None):
    """Create a minimal Orchestrator for testing context management."""
    from orchestrator.core.orchestrator import Orchestrator

    config = {
        "logging": {"level": "WARNING", "file": "/dev/null", "console": False},
        "context_management": {
            "enabled": True,
            "budget_ratio": 0.75,
            "preserve_recent_turns": 2,
        },
    }
    if config_overrides:
        config.update(config_overrides)

    with patch.object(Orchestrator, "_setup_logging"):
        orch = Orchestrator(config)

    # Set up mock llm_client with model attribute
    orch.llm_client = MagicMock()
    orch.llm_client.model = "claude-sonnet-4-20250514"
    # Default: no tool_registry or summarizer (existing tests keep passing)
    orch.tool_registry = None
    orch.summarizer = None
    return orch


def _tool_result_msg(tool_use_id: str, content: str) -> dict:
    """Create a user message with a tool_result block."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            }
        ],
    }


def _assistant_tool_use_msg(tool_name: str, tool_use_id: str) -> dict:
    """Create an assistant message with a tool_use block (SDK-style object)."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_use_id
    return {"role": "assistant", "content": [block]}


def _context() -> dict:
    """Minimal context dict for _manage_context_window."""
    return {
        "task_description": "Test task",
        "tools": [],
    }


class TestObservationMasking:
    """Tests for Observation Masking (Layer 1)."""

    @pytest.mark.asyncio
    async def test_old_tool_results_get_masked(self):
        """Tool results older than preserve_recent_turns should be masked."""
        orch = _make_orchestrator()

        # Build 6 messages = 3 turns (assistant + user each)
        # preserve_recent_turns=2 → mask boundary = 6 - 4 = 2 → first 2 msgs get masked
        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 500),  # old, should be masked
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 500),  # recent, keep
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 500),  # recent, keep
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # First tool result (index 1) should be masked (truncated since no tool_registry)
        block = result[1]["content"][0]
        assert "truncated" in block["content"] or "masked" in block["content"]
        assert "500" in block["content"]

        # Recent tool results should be intact
        assert result[3]["content"][0]["content"] == "y" * 500
        assert result[5]["content"][0]["content"] == "z" * 500

    @pytest.mark.asyncio
    async def test_recent_tool_results_preserved(self):
        """Tool results within preserve_recent_turns should not be masked."""
        orch = _make_orchestrator()

        # 4 messages = 2 turns, preserve_recent=2, so mask_boundary=0 → nothing masked
        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 500),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 500),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # Both should be intact
        assert result[1]["content"][0]["content"] == "x" * 500
        assert result[3]["content"][0]["content"] == "y" * 500

    @pytest.mark.asyncio
    async def test_small_tool_results_not_masked(self):
        """Tool results <= 200 chars should not be masked even if old."""
        orch = _make_orchestrator()

        history = [
            _assistant_tool_use_msg("bash", "id-1"),
            _tool_result_msg("id-1", "short output"),  # < 200 chars, skip
            _assistant_tool_use_msg("file_read", "id-2"),
            _tool_result_msg("id-2", "recent"),
            _assistant_tool_use_msg("bash", "id-3"),
            _tool_result_msg("id-3", "also recent"),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # Short old result should NOT be masked
        assert result[1]["content"][0]["content"] == "short output"

    @pytest.mark.asyncio
    async def test_disabled_config_skips_processing(self):
        """When context_management.enabled is false, history is returned as-is."""
        orch = _make_orchestrator({
            "context_management": {"enabled": False},
        })

        big_content = "x" * 10000
        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", big_content),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "recent"),
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "recent2"),
        ]

        result = await orch._manage_context_window(history, _context())
        assert result[1]["content"][0]["content"] == big_content

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """Empty conversation history should be returned as-is."""
        orch = _make_orchestrator()
        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window([], _context())
        assert result == []


class TestEmergencyDrop:
    """Tests for emergency drop (Layer 2)."""

    @pytest.mark.asyncio
    async def test_emergency_drop_when_over_budget(self):
        """When masking isn't enough, oldest turns should be dropped."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.001,  # Very tight budget to trigger drop
                "preserve_recent_turns": 1,
            },
        })

        # 6 messages = 3 turns, preserve 1 turn (2 msgs)
        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 300),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 300),
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 300),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # Should have a context management summary message at the start
        assert "[Context management:" in result[0]["content"]
        # Recent turn (last 2 messages) should still be present
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_no_drop_when_under_budget(self):
        """History under budget should not be dropped."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.75,
                "preserve_recent_turns": 2,
            },
        })

        # Small history, well under budget
        history = [
            _assistant_tool_use_msg("bash", "id-1"),
            _tool_result_msg("id-1", "ok"),
            {"role": "assistant", "content": "Done."},
            {"role": "user", "content": "Thanks"},
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        assert len(result) == 4  # No messages dropped


class TestExtractToolName:
    """Tests for _extract_tool_name helper."""

    def test_extracts_name_from_preceding_assistant(self):
        orch = _make_orchestrator()
        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "content"),
        ]
        assert orch._extract_tool_name(history, 1) == "file_read"

    def test_returns_default_when_no_preceding(self):
        orch = _make_orchestrator()
        history = [_tool_result_msg("id-1", "content")]
        assert orch._extract_tool_name(history, 0) == "tool"

    def test_returns_default_for_text_assistant_msg(self):
        orch = _make_orchestrator()
        history = [
            {"role": "assistant", "content": "Let me help."},
            _tool_result_msg("id-1", "content"),
        ]
        assert orch._extract_tool_name(history, 1) == "tool"


class TestTokenTrackingFix:
    """Tests for the token tracking bug fix."""

    def test_usage_has_input_output_tokens(self):
        """Verify the pattern used for token counting works with real usage format."""
        usage = {"input_tokens": 1500, "output_tokens": 300}
        token_count = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        assert token_count == 1800

    def test_usage_missing_keys_returns_zero(self):
        """If usage dict is empty, token count should be 0, not 'unknown'."""
        usage = {}
        token_count = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        assert token_count == 0


class TestIdempotencyAwareMasking:
    """Tests for idempotency-aware observation masking."""

    @pytest.mark.asyncio
    async def test_idempotent_tool_gets_rerun_mask(self):
        """Idempotent tools should get 'Re-run the tool' mask message."""
        orch = _make_orchestrator()

        # Set up tool_registry mock returning idempotent=True
        mock_tool = MagicMock()
        mock_tool.definition.idempotent = True
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool
        orch.tool_registry = mock_registry

        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 500),  # old, idempotent → re-run mask
            _assistant_tool_use_msg("file_read", "id-2"),
            _tool_result_msg("id-2", "y" * 500),  # recent, keep
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 500),  # recent, keep
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        block = result[1]["content"][0]
        assert "Re-run the tool" in block["content"]
        assert "Observation masked" in block["content"]
        assert "500 chars" in block["content"]

    @pytest.mark.asyncio
    async def test_non_idempotent_tool_gets_truncated(self):
        """Non-idempotent tools should preserve first N chars + truncation notice."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.75,
                "preserve_recent_turns": 2,
                "non_idempotent_truncation": 500,
            },
        })

        mock_tool = MagicMock()
        mock_tool.definition.idempotent = False
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool
        orch.tool_registry = mock_registry

        original = "A" * 1000
        history = [
            _assistant_tool_use_msg("bash", "id-1"),
            _tool_result_msg("id-1", original),  # old, non-idempotent → truncate
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "recent"),
            _assistant_tool_use_msg("bash", "id-3"),
            _tool_result_msg("id-3", "recent2"),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        block = result[1]["content"][0]
        content = block["content"]
        # Should start with first 500 chars
        assert content.startswith("A" * 500)
        assert "truncated from 1000 chars" in content
        assert "cannot be re-run" in content
        assert "bash" in content

    @pytest.mark.asyncio
    async def test_unknown_tool_treated_as_non_idempotent(self):
        """Unknown tools (registry returns None) should be treated as non-idempotent."""
        orch = _make_orchestrator()

        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        orch.tool_registry = mock_registry

        history = [
            _assistant_tool_use_msg("unknown_tool", "id-1"),
            _tool_result_msg("id-1", "B" * 600),  # old, unknown → truncate
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "recent"),
            _assistant_tool_use_msg("bash", "id-3"),
            _tool_result_msg("id-3", "recent2"),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        block = result[1]["content"][0]
        assert "truncated" in block["content"]
        assert "cannot be re-run" in block["content"]


class TestHybridSummarization:
    """Tests for LLM summarization before emergency drop."""

    @pytest.mark.asyncio
    async def test_emergency_drop_calls_summarizer(self):
        """When emergency drop triggers, summarizer.summarize_turns should be called."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.001,  # Trigger emergency drop
                "preserve_recent_turns": 1,
                "summarize_dropped_turns": True,
            },
        })

        mock_summarizer = AsyncMock()
        mock_summarizer.summarize_turns.return_value = "Used file_read to check config. Found API key missing."
        orch.summarizer = mock_summarizer

        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 300),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 300),
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 300),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # Summarizer should have been called
        mock_summarizer.summarize_turns.assert_called_once()
        # Summary should appear in the context management message
        assert "Summary of dropped context" in result[0]["content"]
        assert "API key missing" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_emergency_drop_fallback_without_summarizer(self):
        """Without a summarizer, emergency drop should use generic message."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.001,
                "preserve_recent_turns": 1,
            },
        })
        orch.summarizer = None

        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 300),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 300),
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 300),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        assert "[Context management:" in result[0]["content"]
        assert "dropped to stay within context limits" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_emergency_drop_fallback_on_summarizer_error(self):
        """If summarizer raises an exception, fall back to generic message."""
        orch = _make_orchestrator({
            "context_management": {
                "enabled": True,
                "budget_ratio": 0.001,
                "preserve_recent_turns": 1,
                "summarize_dropped_turns": True,
            },
        })

        mock_summarizer = AsyncMock()
        mock_summarizer.summarize_turns.side_effect = RuntimeError("LLM unavailable")
        orch.summarizer = mock_summarizer

        history = [
            _assistant_tool_use_msg("file_read", "id-1"),
            _tool_result_msg("id-1", "x" * 300),
            _assistant_tool_use_msg("bash", "id-2"),
            _tool_result_msg("id-2", "y" * 300),
            _assistant_tool_use_msg("file_read", "id-3"),
            _tool_result_msg("id-3", "z" * 300),
        ]

        with patch.object(orch, '_build_system_prompt', return_value="system"):
            result = await orch._manage_context_window(history, _context())

        # Should fall back to generic message despite error
        assert "[Context management:" in result[0]["content"]
        assert "dropped to stay within context limits" in result[0]["content"]
