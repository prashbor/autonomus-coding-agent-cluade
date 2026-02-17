"""Claude session wrapper using AWS Bedrock with tool use."""

from typing import Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

import anthropic

from ..config import bedrock_config

if TYPE_CHECKING:
    from ..services.cost_tracker import CostTracker

from .tools import TOOL_DEFINITIONS, ToolExecutor


@dataclass
class SessionMessage:
    """A message in the session history."""

    role: str  # "user" or "assistant"
    content: Any  # Can be string or list of content blocks


@dataclass
class SessionResult:
    """Result from a session query."""

    content: str
    messages: list = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    tool_calls_made: int = 0


class AgentSession:
    """Wraps Anthropic Bedrock client for agent sessions with tool use.

    Each instance represents ONE agent session with its own context window.
    Claude can use tools to read/write files and execute commands.
    """

    def __init__(
        self,
        working_directory: str,
        system_prompt: Optional[str] = None,
        max_turns: int = 50,
        model_id: Optional[str] = None,
        tool_definitions: Optional[list] = None,
        tool_executor: Optional[Any] = None,
        cost_tracker: Optional["CostTracker"] = None,
        cost_phase: str = "develop",
        cost_label_prefix: str = "",
    ):
        """Initialize agent session.

        Args:
            working_directory: Directory where the agent will work
            system_prompt: Custom system prompt for the session
            max_turns: Maximum tool-use turns before stopping
            model_id: Override model ID (defaults to bedrock_config.model_id)
            tool_definitions: Override tool definitions (defaults to TOOL_DEFINITIONS)
            tool_executor: Override tool executor (defaults to new ToolExecutor)
            cost_tracker: Optional CostTracker for recording API costs
            cost_phase: Phase label for cost tracking (plan, feature, develop)
            cost_label_prefix: Prefix for cost entry labels (e.g., feature ID)
        """
        self.working_directory = working_directory
        self.system_prompt = system_prompt
        self.max_turns = max_turns

        # Track messages for API calls
        self.messages: list[dict] = []
        self._total_chars = 0
        self._tool_calls = 0

        # Track real token usage from API responses
        self._turn_usage: list[dict] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Cost tracking
        self._cost_tracker = cost_tracker
        self._cost_phase = cost_phase
        self._cost_label_prefix = cost_label_prefix

        # Initialize Bedrock client
        self.client = anthropic.AnthropicBedrock(
            aws_region=bedrock_config.region,
        )
        # Allow per-session model override
        self.model_id = model_id or bedrock_config.model_id

        # Allow per-session tool override
        self._tool_definitions = tool_definitions or TOOL_DEFINITIONS
        self.tool_executor = tool_executor or ToolExecutor(working_directory)

    async def send_message(self, prompt: str) -> SessionResult:
        """Send a message to Claude via Bedrock and get response.

        Handles tool use loop - Claude can call tools multiple times
        until it's done implementing the feature.

        Args:
            prompt: The prompt to send

        Returns:
            SessionResult with the final response
        """
        # Add user message
        self.messages.append({"role": "user", "content": prompt})
        self._total_chars += len(prompt)

        try:
            final_text = ""
            turns = 0

            while turns < self.max_turns:
                turns += 1

                # Query Claude via Bedrock with tools
                response = self.client.messages.create(
                    model=self.model_id,
                    max_tokens=8192,
                    system=self.system_prompt or "",
                    tools=self._tool_definitions,
                    messages=self.messages,
                )

                # Capture real token usage from API response
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self._total_input_tokens += input_tokens
                self._total_output_tokens += output_tokens
                self._turn_usage.append({
                    "turn": turns,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })

                # Record cost if tracker is available
                if self._cost_tracker:
                    label = f"{self._cost_label_prefix} turn {turns}".strip()
                    entry = self._cost_tracker.record(
                        model_id=self.model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        phase=self._cost_phase,
                        label=label,
                    )
                    self._cost_tracker.print_turn_summary(entry, turns)
                else:
                    print(f"      📊 Turn {turns}: {input_tokens:,} in / {output_tokens:,} out")

                # Process response content blocks
                assistant_content = []
                text_response = ""

                for block in response.content:
                    if block.type == "text":
                        text_response += block.text
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                # Add assistant response to messages
                self.messages.append({"role": "assistant", "content": assistant_content})
                self._total_chars += len(str(assistant_content))

                # Check if Claude wants to use tools
                if response.stop_reason == "tool_use":
                    # Execute tools and send results back
                    tool_results = []

                    for block in response.content:
                        if block.type == "tool_use":
                            self._tool_calls += 1
                            print(f"   🔧 Tool: {block.name}")

                            # Execute the tool
                            result = self.tool_executor.execute(
                                block.name,
                                block.input
                            )

                            # Track tool result size
                            self._total_chars += len(result)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                            # Print brief summary
                            if block.name == "write_file":
                                print(f"      → Writing: {block.input.get('path', 'unknown')}")
                            elif block.name == "read_file":
                                print(f"      → Reading: {block.input.get('path', 'unknown')}")
                            elif block.name == "execute_command":
                                cmd = block.input.get('command', 'unknown')
                                print(f"      → Running: {cmd[:50]}...")
                            elif block.name == "list_directory":
                                print(f"      → Listing: {block.input.get('path', '.')}")

                    # Add tool results to messages
                    self.messages.append({"role": "user", "content": tool_results})

                else:
                    # Claude is done (stop_reason == "end_turn" or other)
                    final_text = text_response
                    break

            # Track final response
            self._total_chars += len(final_text)

            return SessionResult(
                content=final_text,
                messages=self.messages,
                success=True,
                tool_calls_made=self._tool_calls,
            )

        except Exception as e:
            return SessionResult(
                content="",
                success=False,
                error=str(e),
                tool_calls_made=self._tool_calls,
            )

    async def send_message_streaming(self, prompt: str) -> SessionResult:
        """Send a message with streaming response.

        Note: Streaming with tool use is more complex, falls back to non-streaming.

        Args:
            prompt: The prompt to send

        Returns:
            SessionResult with the full response
        """
        # For tool use, we use non-streaming for simplicity
        return await self.send_message(prompt)

    def estimate_tokens_used(self) -> int:
        """Estimate total tokens in current session.

        Uses heuristic of ~4 characters per token.
        """
        return self._total_chars // 4

    def get_total_input_tokens(self) -> int:
        """Get total input tokens from actual API usage data."""
        return self._total_input_tokens

    def get_total_output_tokens(self) -> int:
        """Get total output tokens from actual API usage data."""
        return self._total_output_tokens

    def get_turn_usage(self) -> list[dict]:
        """Get per-turn token usage data."""
        return self._turn_usage.copy()

    def get_message_count(self) -> int:
        """Get the number of messages in the session."""
        return len(self.messages)

    def get_tool_call_count(self) -> int:
        """Get the number of tool calls made."""
        return self._tool_calls

    def reset(self) -> None:
        """Reset the session state."""
        self.messages = []
        self._total_chars = 0
        self._tool_calls = 0
        self._turn_usage = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def get_last_response(self) -> Optional[str]:
        """Get the last assistant text response."""
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")
                elif isinstance(content, str):
                    return content
        return None


class SessionManager:
    """Manages multiple agent sessions."""

    def __init__(self, working_directory: str):
        """Initialize session manager.

        Args:
            working_directory: Base working directory
        """
        self.working_directory = working_directory
        self._sessions: dict[str, AgentSession] = {}

    def create_session(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
        working_dir: Optional[str] = None,
    ) -> AgentSession:
        """Create a new session.

        Args:
            session_id: Unique identifier for the session
            system_prompt: Custom system prompt
            working_dir: Override working directory

        Returns:
            New AgentSession instance
        """
        session = AgentSession(
            working_directory=working_dir or self.working_directory,
            system_prompt=system_prompt,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close and remove a session.

        Returns True if session existed and was removed.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_all_sessions(self) -> dict[str, AgentSession]:
        """Get all active sessions."""
        return self._sessions.copy()
