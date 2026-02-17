"""GitHub repository initialization service for new projects."""

import subprocess
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from ..models.feature import FeatureList


class GitHubRepoInitializer:
    """Service for initializing GitHub repositories for new projects."""

    def __init__(self, working_directory: str):
        """Initialize the GitHub repository initializer.

        Args:
            working_directory: Path to the project directory
        """
        self.working_dir = Path(working_directory)

    async def initialize_github_repo(self, feature_list: FeatureList, private: bool = True) -> Dict[str, Any]:
        """Initialize GitHub repository for new project.

        Args:
            feature_list: Feature list containing project information
            private: Whether to create private repository (default: True)

        Returns:
            Repository information including URL and setup status
        """
        print("🚀 Initializing GitHub repository for new project...")

        repo_info = {
            "name": self._generate_repo_name(feature_list.project_name),
            "description": feature_list.description,
            "private": private,
            "url": None,
            "clone_url": None,
            "initialized": False
        }

        # Step 1: Check if we're already in a git repository
        if not self._is_git_repo():
            await self._initialize_git_repo()

        # Step 2: Check if remote GitHub repository already exists
        existing_remote = self._get_remote_url()
        if existing_remote:
            print(f"✅ Found existing remote repository: {existing_remote}")
            repo_info["url"] = existing_remote
            repo_info["clone_url"] = existing_remote
            repo_info["initialized"] = True
            return repo_info

        # Step 3: Create GitHub repository
        try:
            repo_data = await self._create_github_repo(
                repo_name=repo_info["name"],
                description=repo_info["description"],
                private=private
            )
            repo_info.update(repo_data)

            # Step 4: Add remote origin
            await self._add_remote_origin(repo_info["clone_url"])

            # Step 5: Create initial commit if needed
            await self._create_initial_commit_if_needed()

            # Step 6: Push to remote
            await self._push_to_remote()

            repo_info["initialized"] = True
            print(f"✅ GitHub repository initialized: {repo_info['url']}")

        except Exception as e:
            print(f"❌ Failed to initialize GitHub repository: {e}")
            # Continue without GitHub repository (local development only)
            repo_info["error"] = str(e)

        return repo_info

    def _generate_repo_name(self, project_name: str) -> str:
        """Generate a valid GitHub repository name."""
        # Convert to lowercase, replace spaces/special chars with hyphens
        repo_name = project_name.lower()
        repo_name = ''.join(c if c.isalnum() else '-' for c in repo_name)
        # Remove consecutive hyphens and leading/trailing hyphens
        while '--' in repo_name:
            repo_name = repo_name.replace('--', '-')
        repo_name = repo_name.strip('-')

        # Ensure it's not empty and doesn't start with a number
        if not repo_name or repo_name[0].isdigit():
            repo_name = f"project-{repo_name}"

        return repo_name

    def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        return (self.working_dir / ".git").exists()

    def _get_remote_url(self) -> Optional[str]:
        """Get existing remote URL if it exists."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.working_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    async def _initialize_git_repo(self):
        """Initialize git repository locally."""
        print("📁 Initializing local git repository...")

        result = subprocess.run(
            ["git", "init"],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to initialize git repository: {result.stderr}")

        # Set default branch to main
        subprocess.run(
            ["git", "config", "init.defaultBranch", "main"],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

    async def _create_github_repo(self, repo_name: str, description: str, private: bool) -> Dict[str, str]:
        """Create GitHub repository using GitHub CLI."""
        print(f"🌐 Creating GitHub repository: {repo_name}")

        # Build gh repo create command
        cmd = [
            "gh", "repo", "create", repo_name,
            "--description", description,
            "--source", ".",
        ]

        if private:
            cmd.append("--private")
        else:
            cmd.append("--public")

        result = subprocess.run(
            cmd,
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to create GitHub repository: {result.stderr}")

        # Parse the output to get repository URL
        output_lines = result.stderr.strip().split('\n')  # gh outputs to stderr
        repo_url = None
        for line in output_lines:
            if "https://github.com" in line:
                repo_url = line.strip()
                break

        if not repo_url:
            # Fallback: construct URL from repo name and current user
            user_info = self._get_github_user()
            if user_info:
                repo_url = f"https://github.com/{user_info}/{repo_name}"

        return {
            "url": repo_url,
            "clone_url": repo_url.replace("https://github.com/", "git@github.com:") + ".git" if repo_url else None
        }

    def _get_github_user(self) -> Optional[str]:
        """Get current GitHub username."""
        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    async def _add_remote_origin(self, clone_url: str):
        """Add remote origin to local repository."""
        if not clone_url:
            return

        print("🔗 Adding remote origin...")

        # Remove existing remote if it exists
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        # Add new remote
        result = subprocess.run(
            ["git", "remote", "add", "origin", clone_url],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to add remote origin: {result.stderr}")

    async def _create_initial_commit_if_needed(self):
        """Create initial commit if repository is empty."""
        # Check if there are any commits
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:  # No commits yet
            print("📝 Creating initial commit...")

            # Create .gitignore if it doesn't exist
            gitignore_path = self.working_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_content = """# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Agent files
.agent-state.json
comprehensive_test_report.json
smart_pr_plan.json
"""
                with open(gitignore_path, 'w') as f:
                    f.write(gitignore_content)

            # Create README.md if it doesn't exist
            readme_path = self.working_dir / "README.md"
            if not readme_path.exists():
                with open(readme_path, 'w') as f:
                    f.write(f"# {self.working_dir.name}\n\nGenerated by Autonomous Coding Agent\n")

            # Stage and commit
            subprocess.run(["git", "add", "."], cwd=self.working_dir)
            subprocess.run([
                "git", "commit", "-m", "Initial commit\n\n🤖 Generated by Autonomous Coding Agent"
            ], cwd=self.working_dir)

    async def _push_to_remote(self):
        """Push local repository to remote."""
        print("⬆️ Pushing to remote repository...")

        # Push main branch with upstream
        result = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Try pushing HEAD if main doesn't exist
            current_branch = self._get_current_branch()
            if current_branch and current_branch != "main":
                result = subprocess.run(
                    ["git", "push", "-u", "origin", current_branch],
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True
                )

            if result.returncode != 0:
                raise Exception(f"Failed to push to remote: {result.stderr}")

    def _get_current_branch(self) -> Optional[str]:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.working_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def can_create_github_repo(self) -> bool:
        """Check if GitHub CLI is available and user is authenticated."""
        try:
            # Check if gh CLI is installed
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return False

            # Check if user is authenticated
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0

        except Exception:
            return False