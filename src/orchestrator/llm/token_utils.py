"""Token estimation utilities for context window management."""


MODEL_CONTEXT_WINDOWS = {
    "claude-sonnet-4-20250514": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-opus-4-6": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 200_000


def estimate_tokens(text: str) -> int:
    """Estimate token count. ~4 chars per token for English."""
    return len(text) // 4 + 1


def estimate_message_tokens(messages: list[dict]) -> int:
    """Estimate total tokens for a list of Anthropic API messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += estimate_tokens(str(block.get("content", "")))
                    total += estimate_tokens(str(block.get("input", "")))
                else:
                    # Anthropic SDK objects (TextBlock, ToolUseBlock)
                    total += estimate_tokens(str(block))
        total += 4  # message overhead
    return total


def get_context_window(model: str) -> int:
    """Get context window size for a model."""
    return MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW)
