"""Manage Git branches for feature development."""

import re
import subprocess
from pathlib import Path
from typing import Optional


class BranchManager:
    """Manages Git branch creation and switching for feature development."""

    def __init__(self, repo_path: str):
        """Initialize branch manager with repository path."""
        self.repo_path = Path(repo_path)

    def generate_branch_name(
        self, jira_ticket: str, description: str, max_length: int = 60
    ) -> str:
        """Generate a branch name from Jira ticket and description.

        Format: feature/<JIRA-TICKET>-<short-description>
        Example: feature/TASK-456-add-csv-export
        """
        # Clean and slugify description
        slug = self._slugify(description)

        # Calculate max slug length
        prefix = f"feature/{jira_ticket}-"
        max_slug_length = max_length - len(prefix)

        # Truncate slug if needed
        if len(slug) > max_slug_length:
            slug = slug[:max_slug_length].rstrip("-")

        return f"{prefix}{slug}"

    def _slugify(self, text: str) -> str:
        """Convert text to a URL/branch-friendly slug."""
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    def get_current_branch(self) -> Optional[str]:
        """Get the current branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists locally or remotely."""
        try:
            # Check local branches
            result = subprocess.run(
                ["git", "branch", "--list", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                return True

            # Check remote branches
            result = subprocess.run(
                ["git", "branch", "-r", "--list", f"*/{branch_name}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False

    def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Create a new branch from the base branch.

        Returns True if successful, False otherwise.
        """
        try:
            print(f"📡 Fetching latest changes from remote...")
            # Fetch latest from remote
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=self.repo_path,
                capture_output=True,
                check=False,  # Don't fail if no remote
            )

            # Try to checkout base branch first
            print(f"🔄 Switching to base branch: {base_branch}")
            try:
                subprocess.run(
                    ["git", "checkout", base_branch],
                    cwd=self.repo_path,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                # Try with origin/ prefix
                try:
                    subprocess.run(
                        ["git", "checkout", "-b", base_branch, f"origin/{base_branch}"],
                        cwd=self.repo_path,
                        capture_output=True,
                        check=True,
                    )
                except subprocess.CalledProcessError:
                    # Stay on current branch
                    pass

            # Pull latest changes
            print(f"⬇️  Pulling latest changes from {base_branch}...")
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=self.repo_path,
                capture_output=True,
                check=False,
            )

            # Create and checkout new branch
            print(f"🌿 Creating feature branch: {branch_name}")
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )

            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to create branch: {e}")
            return False

    def checkout_branch(self, branch_name: str) -> bool:
        """Checkout an existing branch.

        Returns True if successful, False otherwise.
        """
        try:
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to checkout branch: {e}")
            return False

    def ensure_branch(
        self, branch_name: str, base_branch: str = "main"
    ) -> bool:
        """Ensure we're on the specified branch, creating it if needed.

        Returns True if successful, False otherwise.
        """
        current = self.get_current_branch()

        if current == branch_name:
            return True

        if self.branch_exists(branch_name):
            return self.checkout_branch(branch_name)
        else:
            return self.create_branch(branch_name, base_branch)

    def get_default_branch(self) -> str:
        """Get the default branch name (main or master)."""
        try:
            # Try to get default branch from remote
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # Extract branch name from refs/remotes/origin/main
                ref = result.stdout.strip()
                return ref.split("/")[-1]
        except Exception:
            pass

        # Check if main exists
        if self.branch_exists("main"):
            return "main"
        elif self.branch_exists("master"):
            return "master"

        return "main"
