"""Git operations for committing and managing changes."""

import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class CommitResult:
    """Result of a git commit operation."""

    success: bool
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None


class GitManager:
    """Manages Git operations for the autonomous coding agent."""

    def __init__(self, repo_path: str):
        """Initialize Git manager with repository path."""
        self.repo_path = Path(repo_path)

    def is_git_repo(self) -> bool:
        """Check if the path is a Git repository."""
        git_dir = self.repo_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def init_repo(self) -> bool:
        """Initialize a new Git repository."""
        try:
            subprocess.run(
                ["git", "init"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_status(self) -> dict:
        """Get the current Git status."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            status = {
                "modified": [],
                "added": [],
                "deleted": [],
                "untracked": [],
            }

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                code = line[:2]
                filepath = line[3:]

                if code == "??":
                    status["untracked"].append(filepath)
                elif "M" in code:
                    status["modified"].append(filepath)
                elif "A" in code:
                    status["added"].append(filepath)
                elif "D" in code:
                    status["deleted"].append(filepath)

            return status
        except subprocess.CalledProcessError:
            return {"modified": [], "added": [], "deleted": [], "untracked": []}

    def has_changes(self) -> bool:
        """Check if there are any uncommitted changes."""
        status = self.get_status()
        return any(
            status["modified"]
            or status["added"]
            or status["deleted"]
            or status["untracked"]
        )

    def stage_all(self) -> bool:
        """Stage all changes for commit."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def stage_files(self, files: list[str]) -> bool:
        """Stage specific files for commit."""
        if not files:
            return True

        try:
            subprocess.run(
                ["git", "add"] + files,
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def commit(self, message: str) -> CommitResult:
        """Create a commit with the given message."""
        try:
            # Stage all changes first
            self.stage_all()

            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Get commit hash
            commit_hash = self.get_last_commit_hash()

            return CommitResult(success=True, commit_hash=commit_hash)
        except subprocess.CalledProcessError as e:
            return CommitResult(
                success=False,
                error_message=e.stderr if e.stderr else str(e),
            )

    def get_last_commit_hash(self) -> Optional[str]:
        """Get the hash of the last commit."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()[:7]  # Short hash
        except subprocess.CalledProcessError:
            return None

    def get_last_commit_message(self) -> Optional[str]:
        """Get the message of the last commit."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def create_feature_commit(
        self,
        feature_id: str,
        feature_name: str,
        project_name: str,
        jira_ticket: Optional[str] = None,
        repo_name: Optional[str] = None,
        files: Optional[list[str]] = None,
        related_commits: Optional[dict[str, str]] = None,
    ) -> CommitResult:
        """Create a commit with feature metadata.

        Generates a commit message in the format:
        feat(FEAT-001): Feature Name

        Part of: project-name
        Jira: TICKET-123
        Repo: repo-name

        Files:
        - file1.py
        - file2.py

        Generated by Autonomous Coding Agent
        """
        # Build commit message
        lines = [f"feat({feature_id}): {feature_name}", ""]

        lines.append(f"Part of: {project_name}")

        if jira_ticket:
            lines.append(f"Jira: {jira_ticket}")

        if repo_name:
            lines.append(f"Repo: {repo_name}")

        if related_commits:
            lines.append("")
            lines.append("Related commits:")
            for repo, hash in related_commits.items():
                lines.append(f"- {repo}: {hash}")

        if files:
            lines.append("")
            lines.append("Files:")
            for f in files[:10]:  # Limit to 10 files
                lines.append(f"- {f}")
            if len(files) > 10:
                lines.append(f"- ... and {len(files) - 10} more")

        lines.append("")
        lines.append("Generated by Autonomous Coding Agent")

        message = "\n".join(lines)

        return self.commit(message)

    def create_wip_commit(
        self,
        feature_id: str,
        feature_name: str,
        project_name: str,
        jira_ticket: Optional[str] = None,
        repo_name: Optional[str] = None,
        files: Optional[list[str]] = None,
    ) -> CommitResult:
        """Create a WIP commit for a feature that failed validation.

        Uses 'wip(FEAT-001):' prefix instead of 'feat(FEAT-001):'.
        """
        lines = [f"wip({feature_id}): {feature_name} [validation failed]", ""]
        lines.append(f"Part of: {project_name}")
        lines.append("Status: Feature implementation incomplete - validation failed")

        if jira_ticket:
            lines.append(f"Jira: {jira_ticket}")
        if repo_name:
            lines.append(f"Repo: {repo_name}")
        if files:
            lines.append("")
            lines.append("Files:")
            for f in files[:10]:
                lines.append(f"- {f}")
            if len(files) > 10:
                lines.append(f"- ... and {len(files) - 10} more")

        lines.append("")
        lines.append("Generated by Autonomous Coding Agent (WIP - needs manual review)")

        message = "\n".join(lines)
        return self.commit(message)

    def get_changed_files(self) -> list[str]:
        """Get list of files that have been changed."""
        status = self.get_status()
        return (
            status["modified"]
            + status["added"]
            + status["deleted"]
            + status["untracked"]
        )

    def reset_hard(self) -> bool:
        """Reset all changes (dangerous - discards all uncommitted changes)."""
        try:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def stash(self) -> bool:
        """Stash current changes."""
        try:
            subprocess.run(
                ["git", "stash"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def stash_pop(self) -> bool:
        """Pop stashed changes."""
        try:
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
