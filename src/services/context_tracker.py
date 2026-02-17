"""Track context window usage for session management."""

from typing import Optional


class ContextTracker:
    """Tracks estimated token usage to determine when to create new sessions.

    Uses a simple heuristic: ~4 characters per token.
    """

    # Default thresholds
    DEFAULT_MAX_TOKENS = 200_000  # Claude's context window
    DEFAULT_THRESHOLD_RATIO = 0.75  # Trigger handoff at 75%

    # Approximate characters per token
    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    ):
        """Initialize context tracker.

        Args:
            max_tokens: Maximum tokens in context window
            threshold_ratio: Ratio at which to trigger handoff (0.0 - 1.0)
        """
        self.max_tokens = max_tokens
        self.threshold_ratio = threshold_ratio
        self.threshold_tokens = int(max_tokens * threshold_ratio)

        # Tracking
        self._total_chars = 0
        self._message_count = 0
        self._tool_call_count = 0

    @property
    def estimated_tokens(self) -> int:
        """Get estimated token count."""
        return self._total_chars // self.CHARS_PER_TOKEN

    @property
    def usage_ratio(self) -> float:
        """Get current usage as a ratio (0.0 - 1.0)."""
        return self.estimated_tokens / self.max_tokens

    @property
    def usage_percent(self) -> float:
        """Get current usage as a percentage."""
        return self.usage_ratio * 100

    @property
    def remaining_tokens(self) -> int:
        """Get estimated remaining tokens before threshold."""
        return max(0, self.threshold_tokens - self.estimated_tokens)

    def should_handoff(self) -> bool:
        """Check if context usage has exceeded threshold."""
        return self.estimated_tokens >= self.threshold_tokens

    def add_message(self, content: str, role: str = "user") -> None:
        """Track a message being added to context.

        Args:
            content: Message content
            role: Message role (user, assistant, system)
        """
        # Add characters from content
        self._total_chars += len(content)

        # Add overhead for message structure
        self._total_chars += 50  # Approximate overhead for role, timestamps, etc.

        self._message_count += 1

    def add_tool_call(self, tool_name: str, input_size: int, output_size: int) -> None:
        """Track a tool call.

        Args:
            tool_name: Name of the tool
            input_size: Size of tool input in characters
            output_size: Size of tool output in characters
        """
        # Tool calls add significant context
        self._total_chars += len(tool_name)
        self._total_chars += input_size
        self._total_chars += output_size
        self._total_chars += 100  # Overhead for tool call structure

        self._tool_call_count += 1

    def add_file_read(self, file_path: str, content_size: int) -> None:
        """Track a file read operation.

        Args:
            file_path: Path to the file
            content_size: Size of file content in characters
        """
        self._total_chars += len(file_path)
        self._total_chars += content_size
        self._total_chars += 50  # Overhead

    def add_file_write(self, file_path: str, content_size: int) -> None:
        """Track a file write operation.

        Args:
            file_path: Path to the file
            content_size: Size of file content in characters
        """
        self._total_chars += len(file_path)
        self._total_chars += content_size
        self._total_chars += 50  # Overhead

    def reset(self) -> None:
        """Reset tracking for a new session."""
        self._total_chars = 0
        self._message_count = 0
        self._tool_call_count = 0

    def get_stats(self) -> dict:
        """Get current tracking statistics."""
        return {
            "estimated_tokens": self.estimated_tokens,
            "max_tokens": self.max_tokens,
            "threshold_tokens": self.threshold_tokens,
            "usage_percent": round(self.usage_percent, 1),
            "remaining_tokens": self.remaining_tokens,
            "message_count": self._message_count,
            "tool_call_count": self._tool_call_count,
            "should_handoff": self.should_handoff(),
        }

    def estimate_feature_capacity(self, avg_feature_tokens: int = 50_000) -> int:
        """Estimate how many more features can fit in current context.

        Args:
            avg_feature_tokens: Average tokens per feature (default 50k)

        Returns:
            Estimated number of features that can fit
        """
        remaining = self.remaining_tokens
        return remaining // avg_feature_tokens if avg_feature_tokens > 0 else 0

    def set_from_state(
        self, estimated_tokens: int, session_count: int
    ) -> None:
        """Set tracker state from saved agent state.

        Args:
            estimated_tokens: Previously estimated token count
            session_count: Number of sessions so far
        """
        self._total_chars = estimated_tokens * self.CHARS_PER_TOKEN

    def get_summary(self) -> str:
        """Get a human-readable summary of context usage."""
        stats = self.get_stats()
        return (
            f"Context: {stats['usage_percent']}% used "
            f"({stats['estimated_tokens']:,}/{stats['max_tokens']:,} tokens), "
            f"{stats['remaining_tokens']:,} remaining before handoff"
        )


class FeatureContextEstimator:
    """Estimates context requirements for features."""

    # Baseline estimates per feature component
    BASE_IMPLEMENTATION = 20_000  # Tokens for basic implementation
    BASE_TESTS = 15_000  # Tokens for writing tests
    TEST_ITERATION = 10_000  # Tokens per test-fix iteration
    MAX_TEST_ITERATIONS = 5  # Maximum test iterations to account for

    @classmethod
    def estimate_feature_tokens(
        cls,
        file_count: int = 1,
        test_count: int = 1,
        complexity: int = 5,  # 1-10 scale
    ) -> int:
        """Estimate tokens needed for a feature.

        Args:
            file_count: Number of files to create/modify
            test_count: Number of test files
            complexity: Complexity on 1-10 scale

        Returns:
            Estimated token count
        """
        # Base implementation
        tokens = cls.BASE_IMPLEMENTATION

        # Scale by file count
        tokens += file_count * 5_000

        # Add test writing
        tokens += cls.BASE_TESTS * test_count

        # Add test iterations (assume 2 iterations on average)
        tokens += cls.TEST_ITERATION * 2

        # Scale by complexity
        complexity_factor = 0.5 + (complexity / 10)
        tokens = int(tokens * complexity_factor)

        return tokens

    @classmethod
    def can_fit_feature(
        cls,
        tracker: ContextTracker,
        file_count: int = 1,
        test_count: int = 1,
        complexity: int = 5,
    ) -> bool:
        """Check if a feature can fit in remaining context.

        Args:
            tracker: Current context tracker
            file_count: Number of files
            test_count: Number of test files
            complexity: Complexity on 1-10 scale

        Returns:
            True if feature likely fits, False otherwise
        """
        estimated = cls.estimate_feature_tokens(file_count, test_count, complexity)
        return tracker.remaining_tokens >= estimated
