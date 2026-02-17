"""Pull Request models for smart PR grouping and management."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PRGroup(BaseModel):
    """A group of features that should be combined into a single Pull Request."""

    id: str = Field(description="Unique identifier for this PR group")
    name: str = Field(description="Human-readable name for this PR")
    description: str = Field(description="Detailed description of what this PR contains")
    features: List[str] = Field(description="List of Feature IDs included in this PR")
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of PR Group IDs that must be merged before this one"
    )

    # Metrics for review estimation
    estimated_review_time: int = Field(description="Estimated review time in minutes")
    files_changed: int = Field(description="Number of files modified in this PR")
    lines_added: int = Field(description="Estimated lines of code added")
    lines_deleted: int = Field(description="Estimated lines of code deleted")

    # GitHub/Git metadata
    branch_name: Optional[str] = Field(default=None, description="Git branch name for this PR")
    pr_url: Optional[str] = Field(default=None, description="URL of created PR")
    commit_hashes: List[str] = Field(
        default_factory=list,
        description="Git commit hashes included in this PR"
    )
    repository_id: Optional[str] = Field(
        default=None,
        description="Repository ID for multi-repo projects"
    )

    @property
    def net_lines_changed(self) -> int:
        """Calculate net change in lines of code."""
        return self.lines_added + self.lines_deleted

    @property
    def feature_count(self) -> int:
        """Number of features in this PR."""
        return len(self.features)


class PRReviewFocus(BaseModel):
    """Specific areas that reviewers should focus on for a PR."""

    file_path: str = Field(description="Path to file that needs attention")
    line_range: Optional[str] = Field(default=None, description="Specific lines to review (e.g., '45-67')")
    focus_area: str = Field(description="What to focus on (e.g., 'security validation', 'error handling')")
    importance: str = Field(description="Importance level: 'high', 'medium', 'low'")


class SmartPRPlan(BaseModel):
    """Complete plan for organizing features into Pull Requests."""

    project_name: str = Field(description="Name of the project")
    total_features: int = Field(description="Total number of features being organized")
    pr_groups: List[PRGroup] = Field(description="List of PR groups to create")
    review_order: List[str] = Field(
        description="Recommended order for reviewing PRs (by PR Group ID)"
    )

    # Metadata for reporting
    total_estimated_review_time: int = Field(
        description="Sum of estimated review times for all PRs"
    )
    dependency_map: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Map of PR dependencies for visualization"
    )

    @property
    def pr_count(self) -> int:
        """Number of PRs that will be created."""
        return len(self.pr_groups)

    @property
    def average_pr_size(self) -> float:
        """Average number of features per PR."""
        if not self.pr_groups:
            return 0.0
        return self.total_features / len(self.pr_groups)

    def get_pr_by_id(self, pr_id: str) -> Optional[PRGroup]:
        """Get PR group by ID."""
        for pr_group in self.pr_groups:
            if pr_group.id == pr_id:
                return pr_group
        return None

    def get_ready_prs(self, merged_pr_ids: List[str]) -> List[PRGroup]:
        """Get PRs that are ready for review (dependencies satisfied)."""
        ready_prs = []
        for pr_group in self.pr_groups:
            if pr_group.id not in merged_pr_ids:
                # Check if all dependencies are merged
                dependencies_satisfied = all(
                    dep_id in merged_pr_ids
                    for dep_id in pr_group.dependencies
                )
                if dependencies_satisfied:
                    ready_prs.append(pr_group)
        return ready_prs


class PRCreationResult(BaseModel):
    """Result of creating Pull Requests from a Smart PR Plan."""

    plan: SmartPRPlan = Field(description="The original PR plan")
    created_prs: List[str] = Field(description="List of created PR URLs")
    failed_prs: List[str] = Field(
        default_factory=list,
        description="List of PR Group IDs that failed to create"
    )
    creation_timestamp: str = Field(description="When PRs were created")

    @property
    def success_rate(self) -> float:
        """Percentage of PRs successfully created."""
        total_prs = len(self.plan.pr_groups)
        if total_prs == 0:
            return 0.0
        successful_prs = len(self.created_prs)
        return (successful_prs / total_prs) * 100

    @property
    def all_created_successfully(self) -> bool:
        """Check if all PRs were created successfully."""
        return len(self.failed_prs) == 0 and len(self.created_prs) == len(self.plan.pr_groups)