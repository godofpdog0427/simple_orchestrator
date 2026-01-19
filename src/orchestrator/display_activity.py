"""Activity indicator for long-running operations.

This module provides visual feedback during tool execution and LLM waiting periods,
helping users distinguish between "still running" and "hung" states.

Phase 7B: Execution Activity Indicator
"""

import threading
import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner


class ActivityIndicator:
    """
    Display activity indicator during long-running operations.

    Uses Rich's Spinner + Live for animated execution feedback.
    Supports both async context manager and sync start/stop patterns.

    Features:
    - Transient display (auto-clears after completion)
    - Multiple spinner styles (dots, line, arc, circle, etc.)
    - Thread-safe for sync operations
    - Async-compatible for tool execution
    """

    # Available spinner styles
    SPINNER_STYLES = [
        "dots",
        "dots2",
        "dots3",
        "line",
        "line2",
        "arc",
        "circle",
        "bouncingBar",
        "bouncingBall",
        "aesthetic",
    ]

    def __init__(
        self,
        console: Console | None = None,
        spinner_name: str = "dots",
        style: str = "cyan",
        enabled: bool = True,
    ):
        """
        Initialize activity indicator.

        Args:
            console: Rich Console instance (creates new if None)
            spinner_name: Name of spinner animation style
            style: Rich style for spinner color
            enabled: Whether indicator is enabled (can be disabled via config)
        """
        self.console = console or Console()
        self.spinner_name = spinner_name if spinner_name in self.SPINNER_STYLES else "dots"
        self.style = style
        self.enabled = enabled

        self._live: Live | None = None
        self._message: str = ""
        # Use RLock to allow reentrant locking (start() calling update_message())
        self._lock = threading.RLock()
        self._running = False

    @asynccontextmanager
    async def show(self, message: str) -> AsyncIterator[None]:
        """
        Show activity indicator with message (async context manager).

        Usage:
            async with indicator.show("Executing bash command..."):
                result = await tool.execute()

        Args:
            message: Description of current activity
        """
        if not self.enabled:
            yield
            return

        self._message = message
        spinner = Spinner(self.spinner_name, text=f" {message}", style=self.style)

        self._live = Live(
            spinner,
            console=self.console,
            refresh_per_second=10,
            transient=True,  # Auto-clear after completion
        )

        try:
            self._live.start()
            self._running = True
            yield
        finally:
            self._live.stop()
            self._live = None
            self._running = False

    @contextmanager
    def show_sync(self, message: str) -> Iterator[None]:
        """
        Show activity indicator with message (sync context manager).

        Usage:
            with indicator.show_sync("Processing..."):
                do_work()

        Args:
            message: Description of current activity
        """
        if not self.enabled:
            yield
            return

        self._message = message
        spinner = Spinner(self.spinner_name, text=f" {message}", style=self.style)

        self._live = Live(
            spinner,
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )

        try:
            self._live.start()
            self._running = True
            yield
        finally:
            self._live.stop()
            self._live = None
            self._running = False

    def start(self, message: str) -> None:
        """
        Start showing activity indicator (manual control).

        Must call stop() when done.

        Args:
            message: Description of current activity
        """
        if not self.enabled:
            return

        with self._lock:
            if self._running:
                # Already running, just update message
                self.update_message(message)
                return

            self._message = message
            spinner = Spinner(self.spinner_name, text=f" {message}", style=self.style)

            self._live = Live(
                spinner,
                console=self.console,
                refresh_per_second=10,
                transient=True,
            )
            self._live.start()
            self._running = True

    def stop(self) -> None:
        """Stop the activity indicator."""
        with self._lock:
            if self._live and self._running:
                self._live.stop()
                self._live = None
                self._running = False

    def update_message(self, message: str) -> None:
        """
        Update the activity message while running.

        Args:
            message: New message to display
        """
        if not self.enabled or not self._live or not self._running:
            return

        with self._lock:
            self._message = message
            spinner = Spinner(self.spinner_name, text=f" {message}", style=self.style)
            self._live.update(spinner)

    @property
    def is_running(self) -> bool:
        """Check if indicator is currently running."""
        return self._running


class ToolActivityIndicator(ActivityIndicator):
    """
    Specialized activity indicator for tool execution.

    Provides tool-specific message formatting and timeout display.
    """

    def __init__(
        self,
        console: Console | None = None,
        spinner_name: str = "dots",
        style: str = "cyan",
        enabled: bool = True,
    ):
        super().__init__(console, spinner_name, style, enabled)
        self._tool_name: str = ""
        self._start_time: float = 0

    @asynccontextmanager
    async def show_tool(
        self,
        tool_name: str,
        description: str = "",
        timeout: int | None = None,
    ) -> AsyncIterator[None]:
        """
        Show activity indicator for tool execution.

        Args:
            tool_name: Name of the tool being executed
            description: Optional description of tool action
            timeout: Optional timeout in seconds (for display only)
        """
        self._tool_name = tool_name
        self._start_time = time.time()

        # Format message
        if timeout:
            message = f"Executing {tool_name} (timeout: {timeout}s)..."
        elif description:
            message = f"{tool_name}: {description}"
        else:
            message = f"Executing {tool_name}..."

        async with self.show(message):
            yield

    def format_tool_message(
        self,
        tool_name: str,
        args: dict | None = None,
    ) -> str:
        """
        Format a descriptive message for tool execution.

        Args:
            tool_name: Name of the tool
            args: Tool arguments (optional, for context)

        Returns:
            Formatted message string
        """
        if tool_name == "bash":
            cmd = args.get("command", "") if args else ""
            if len(cmd) > 40:
                cmd = cmd[:37] + "..."
            return f"Running: {cmd}" if cmd else "Executing bash..."

        elif tool_name == "file_read":
            path = args.get("path", "") if args else ""
            if path:
                # Show just filename
                filename = path.split("/")[-1]
                return f"Reading: {filename}"
            return "Reading file..."

        elif tool_name == "file_write":
            path = args.get("path", "") if args else ""
            if path:
                filename = path.split("/")[-1]
                return f"Writing: {filename}"
            return "Writing file..."

        elif tool_name == "web_fetch":
            url = args.get("url", "") if args else ""
            if url:
                # Show domain only
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    return f"Fetching: {domain}"
                except Exception:
                    pass
            return "Fetching URL..."

        else:
            return f"Executing {tool_name}..."
