"""Commit management for the autonomous coding agent."""

from typing import Optional
from dataclasses import dataclass

from ..models.feature import Feature, FeatureList
from ..services.git_manager import GitManager, CommitResult


@dataclass
class LinkedCommit:
    """A commit linked to a feature across repositories."""

    repo_id: str
    commit_hash: str
    feature_id: str
    files: list[str]


class CommitManager:
    """Manages commits with feature linking across repositories."""

    def __init__(self, feature_list: FeatureList):
        """Initialize commit manager.

        Args:
            feature_list: The feature list being implemented
        """
        self.feature_list = feature_list
        self.git_managers: dict[str, GitManager] = {}
        self.linked_commits: dict[str, list[LinkedCommit]] = {}

        # Initialize Git managers for each repository
        self._init_git_managers()

    def _init_git_managers(self) -> None:
        """Initialize Git managers for all repositories."""
        if self.feature_list.project_type == "new":
            # New project - single output directory
            if self.feature_list.output_directory:
                self.git_managers["main"] = GitManager(
                    self.feature_list.output_directory
                )
        else:
            # Existing repos
            for repo in self.feature_list.repositories:
                self.git_managers[repo.id] = GitManager(repo.path)

    def get_git_manager(self, repo_id: str = "main") -> Optional[GitManager]:
        """Get Git manager for a repository."""
        return self.git_managers.get(repo_id)

    def create_feature_commit(
        self,
        feature: Feature,
        repo_id: str = "main",
        related_commits: Optional[dict[str, str]] = None,
    ) -> CommitResult:
        """Create a commit for a feature.

        Args:
            feature: The feature being committed
            repo_id: Repository ID to commit to
            related_commits: Related commits from other repos

        Returns:
            CommitResult with success status and hash
        """
        git_manager = self.git_managers.get(repo_id)
        if not git_manager:
            return CommitResult(
                success=False,
                error_message=f"No Git manager for repo: {repo_id}",
            )

        if not git_manager.has_changes():
            return CommitResult(
                success=True,
                commit_hash=None,
                error_message="No changes to commit",
            )

        # Get repo name for commit message
        repo_name = None
        for repo in self.feature_list.repositories:
            if repo.id == repo_id:
                repo_name = repo_id
                break

        # Create the commit
        result = git_manager.create_feature_commit(
            feature_id=feature.id,
            feature_name=feature.name,
            project_name=self.feature_list.project_name,
            jira_ticket=self.feature_list.jira_ticket,
            repo_name=repo_name,
            files=git_manager.get_changed_files(),
            related_commits=related_commits,
        )

        # Track linked commit
        if result.success and result.commit_hash:
            linked = LinkedCommit(
                repo_id=repo_id,
                commit_hash=result.commit_hash,
                feature_id=feature.id,
                files=git_manager.get_changed_files(),
            )

            if feature.id not in self.linked_commits:
                self.linked_commits[feature.id] = []
            self.linked_commits[feature.id].append(linked)

        return result

    def commit_multi_repo_feature(self, feature: Feature) -> dict[str, CommitResult]:
        """Commit a feature across multiple repositories.

        Commits are created in dependency order with linking.

        Args:
            feature: The feature to commit

        Returns:
            Dictionary of repo_id -> CommitResult
        """
        results: dict[str, CommitResult] = {}
        related_commits: dict[str, str] = {}

        # Get repos in order based on dependencies
        repo_order = self._get_repo_order()

        for repo_id in repo_order:
            # Check if this repo has changes for this feature
            git_manager = self.git_managers.get(repo_id)
            if not git_manager or not git_manager.has_changes():
                continue

            # Create commit with links to previous commits
            result = self.create_feature_commit(
                feature=feature,
                repo_id=repo_id,
                related_commits=related_commits.copy() if related_commits else None,
            )

            results[repo_id] = result

            # Track for linking in subsequent commits
            if result.success and result.commit_hash:
                related_commits[repo_id] = result.commit_hash

        return results

    def _get_repo_order(self) -> list[str]:
        """Get repositories in dependency order (upstream first)."""
        if not self.feature_list.repo_dependencies:
            return list(self.git_managers.keys())

        # Build dependency graph
        graph: dict[str, list[str]] = {repo_id: [] for repo_id in self.git_managers}

        for dep in self.feature_list.repo_dependencies:
            if dep.downstream in graph:
                graph[dep.downstream].append(dep.upstream)

        # Topological sort
        visited: set[str] = set()
        order: list[str] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, []):
                visit(dep)
            order.append(node)

        for node in graph:
            visit(node)

        return order

    def get_feature_commits(self, feature_id: str) -> list[LinkedCommit]:
        """Get all commits for a feature."""
        return self.linked_commits.get(feature_id, [])

    def get_all_commits(self) -> dict[str, list[LinkedCommit]]:
        """Get all tracked commits by feature."""
        return self.linked_commits.copy()

    def has_uncommitted_changes(self, repo_id: str = "main") -> bool:
        """Check if a repository has uncommitted changes."""
        git_manager = self.git_managers.get(repo_id)
        return git_manager.has_changes() if git_manager else False

    def has_any_uncommitted_changes(self) -> bool:
        """Check if any repository has uncommitted changes."""
        return any(
            gm.has_changes() for gm in self.git_managers.values()
        )
