"""Tools for Claude to interact with the filesystem and execute commands."""

import os
import subprocess
from pathlib import Path
from typing import Any


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, or overwrites if it does. Creates parent directories automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path relative to working directory"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path relative to working directory"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path relative to working directory. Use '.' for current directory."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "execute_command",
        "description": "Execute a shell command and return the output. Use for running tests, installing dependencies, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "create_directory",
        "description": "Create a directory and any necessary parent directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to create"
                }
            },
            "required": ["path"]
        }
    }
]


# Read-only tools for analysis sessions (safety: no write_file, create_directory, execute_command)
READONLY_TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Returns the full text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path relative to working directory",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a path. Returns entries prefixed with [dir] or [file].",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path relative to working directory. Use '.' for current directory.",
                }
            },
            "required": ["path"],
        },
    },
]


class ToolExecutor:
    """Executes tools requested by Claude."""

    def __init__(self, working_directory: str):
        """Initialize with working directory.

        Args:
            working_directory: Base directory for file operations
        """
        self.working_directory = Path(working_directory).resolve()
        # Ensure working directory exists
        self.working_directory.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory.

        Args:
            path: Relative or absolute path

        Returns:
            Resolved absolute path
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.working_directory / path).resolve()

    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is within working directory (security check).

        Args:
            path: Path to check

        Returns:
            True if path is safe
        """
        try:
            path.resolve().relative_to(self.working_directory)
            return True
        except ValueError:
            return False

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            String result of the tool execution
        """
        try:
            if tool_name == "write_file":
                return self._write_file(tool_input["path"], tool_input["content"])
            elif tool_name == "read_file":
                return self._read_file(tool_input["path"])
            elif tool_name == "list_directory":
                return self._list_directory(tool_input["path"])
            elif tool_name == "execute_command":
                return self._execute_command(tool_input["command"])
            elif tool_name == "create_directory":
                return self._create_directory(tool_input["path"])
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def _write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        file_path = self._resolve_path(path)

        if not self._is_safe_path(file_path):
            return f"Error: Path '{path}' is outside working directory"

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_text(content)

        return f"Successfully wrote {len(content)} bytes to {path}"

    def _read_file(self, path: str) -> str:
        """Read content from a file."""
        file_path = self._resolve_path(path)

        if not self._is_safe_path(file_path):
            return f"Error: Path '{path}' is outside working directory"

        if not file_path.exists():
            return f"Error: File '{path}' does not exist"

        if not file_path.is_file():
            return f"Error: '{path}' is not a file"

        content = file_path.read_text()
        return content

    def _list_directory(self, path: str) -> str:
        """List contents of a directory."""
        dir_path = self._resolve_path(path)

        if not self._is_safe_path(dir_path):
            return f"Error: Path '{path}' is outside working directory"

        if not dir_path.exists():
            return f"Error: Directory '{path}' does not exist"

        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory"

        entries = []
        for entry in sorted(dir_path.iterdir()):
            entry_type = "dir" if entry.is_dir() else "file"
            entries.append(f"[{entry_type}] {entry.name}")

        if not entries:
            return f"Directory '{path}' is empty"

        return "\n".join(entries)

    def _execute_command(self, command: str) -> str:
        """Execute a shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_directory),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            output += f"Return code: {result.returncode}"

            return output if output.strip() else "Command completed with no output"

        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 5 minutes"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _create_directory(self, path: str) -> str:
        """Create a directory."""
        dir_path = self._resolve_path(path)

        if not self._is_safe_path(dir_path):
            return f"Error: Path '{path}' is outside working directory"

        dir_path.mkdir(parents=True, exist_ok=True)

        return f"Successfully created directory: {path}"


class ReadOnlyToolExecutor(ToolExecutor):
    """Tool executor that only allows read operations.

    Used for codebase analysis sessions where we need to explore
    but never modify the target repository.
    """

    def __init__(self, working_directory: str):
        """Initialize with working directory WITHOUT creating it.

        Unlike ToolExecutor, this does NOT call mkdir because
        the analysis target may be a read-only filesystem.
        """
        self.working_directory = Path(working_directory).resolve()

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool, blocking any write operations."""
        if tool_name in ("write_file", "create_directory", "execute_command"):
            return f"Error: Tool '{tool_name}' is not available in read-only analysis mode."
        return super().execute(tool_name, tool_input)
