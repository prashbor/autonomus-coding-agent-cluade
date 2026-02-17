"""AgentState and related Pydantic models for tracking progress."""

from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field


class FeatureStatus(BaseModel):
    """Status of a single feature."""

    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending",
        description="Current status of the feature",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="When work on this feature started",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When the feature was completed",
    )
    commit_hash: Optional[str] = Field(
        default=None,
        description="Git commit hash (for single repo)",
    )
    repo_commits: dict[str, str] = Field(
        default_factory=dict,
        description="Commit hashes per repository (for multi-repo)",
    )
    tests_passed: bool = Field(
        default=False,
        description="Whether all tests passed",
    )
    test_attempts: int = Field(
        default=0,
        description="Number of test attempts",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if failed",
    )


class RepositoryStatus(BaseModel):
    """Status of a repository in multi-repo projects."""

    path: str = Field(description="Path to the repository")
    branch_created: bool = Field(
        default=False,
        description="Whether feature branch was created",
    )
    current_branch: Optional[str] = Field(
        default=None,
        description="Current branch name",
    )
    last_commit: Optional[str] = Field(
        default=None,
        description="Last commit hash",
    )


class ContextTracking(BaseModel):
    """Tracking context usage across sessions."""

    estimated_tokens_used: int = Field(
        default=0,
        description="Estimated tokens used in current session",
    )
    max_tokens_threshold: int = Field(
        default=150000,
        description="Maximum tokens before handoff (75% of ~200k)",
    )
    session_count: int = Field(
        default=0,
        description="Number of sessions so far",
    )
    handoff_triggered: bool = Field(
        default=False,
        description="Whether handoff was triggered in last session",
    )


class CostRecord(BaseModel):
    """A single API call's cost record."""

    model_id: str = Field(description="Bedrock model ID used")
    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    input_cost: float = Field(description="Cost for input tokens in USD")
    output_cost: float = Field(description="Cost for output tokens in USD")
    phase: str = Field(description="Pipeline phase (plan, feature, develop)")
    label: str = Field(description="Human-readable label (e.g., FEAT-001 turn 3)")


class CostTracking(BaseModel):
    """Tracks cumulative API cost across all phases."""

    total_input_tokens: int = Field(
        default=0,
        description="Total input tokens across all API calls",
    )
    total_output_tokens: int = Field(
        default=0,
        description="Total output tokens across all API calls",
    )
    total_cost: float = Field(
        default=0.0,
        description="Total cost in USD",
    )
    phase_costs: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by phase (plan, feature, develop)",
    )
    feature_costs: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by feature ID",
    )
    records: List[CostRecord] = Field(
        default_factory=list,
        description="Full audit trail of all API calls",
    )


class AgentState(BaseModel):
    """Complete state of the autonomous coding agent."""

    session_id: str = Field(description="Unique session identifier")
    project_init_path: str = Field(description="Path to project-init.md")
    feature_list_path: str = Field(description="Path to feature_list.json")
    project_type: Literal["new", "single_repo", "multi_repo"] = Field(
        description="Type of project"
    )
    output_directory: Optional[str] = Field(
        default=None,
        description="Output directory (for new projects)",
    )
    jira_ticket: Optional[str] = Field(
        default=None,
        description="Jira ticket (for existing repos)",
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Feature branch name",
    )
    branch_created: bool = Field(
        default=False,
        description="Whether feature branch was created",
    )
    repositories_status: dict[str, RepositoryStatus] = Field(
        default_factory=dict,
        description="Status of each repository (multi-repo)",
    )
    phase: Literal["planning", "development", "completed"] = Field(
        default="planning",
        description="Current phase",
    )
    features_status: dict[str, FeatureStatus] = Field(
        default_factory=dict,
        description="Status of each feature by ID",
    )
    context_tracking: ContextTracking = Field(
        default_factory=ContextTracking,
        description="Context tracking info",
    )
    cost_tracking: CostTracking = Field(
        default_factory=CostTracking,
        description="API cost tracking across all phases",
    )
    conversation_summary: Optional[str] = Field(
        default=None,
        description="Summary for session handoff",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When the state was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the state was last updated",
    )

    # New fields for comprehensive testing and PR management
    comprehensive_test_report: Optional[str] = Field(
        default=None,
        description="Path to comprehensive test report JSON file",
    )
    smart_pr_plan: Optional[str] = Field(
        default=None,
        description="Path to smart PR plan JSON file",
    )
    created_prs: List[str] = Field(
        default_factory=list,
        description="List of created PR URLs",
    )
    comprehensive_testing_enabled: bool = Field(
        default=False,
        description="Whether comprehensive testing was enabled for this session",
    )
    smart_prs_enabled: bool = Field(
        default=False,
        description="Whether smart PR creation was enabled for this session",
    )

    def get_completed_feature_ids(self) -> set[str]:
        """Get IDs of all completed features."""
        return {
            fid
            for fid, status in self.features_status.items()
            if status.status == "completed"
        }

    def get_in_progress_feature_id(self) -> Optional[str]:
        """Get ID of feature currently in progress."""
        for fid, status in self.features_status.items():
            if status.status == "in_progress":
                return fid
        return None

    def mark_feature_in_progress(self, feature_id: str) -> None:
        """Mark a feature as in progress."""
        if feature_id not in self.features_status:
            self.features_status[feature_id] = FeatureStatus()
        self.features_status[feature_id].status = "in_progress"
        self.features_status[feature_id].started_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_feature_completed(
        self,
        feature_id: str,
        commit_hash: Optional[str] = None,
        repo_commits: Optional[dict[str, str]] = None,
        tests_passed: bool = True,
    ) -> None:
        """Mark a feature as completed.

        Args:
            feature_id: ID of the feature
            commit_hash: Git commit hash (for single repo)
            repo_commits: Commit hashes per repository (for multi-repo)
            tests_passed: Whether all tests passed during validation
        """
        if feature_id not in self.features_status:
            self.features_status[feature_id] = FeatureStatus()
        status = self.features_status[feature_id]
        status.status = "completed"
        status.completed_at = datetime.now()
        status.tests_passed = tests_passed
        if commit_hash:
            status.commit_hash = commit_hash
        if repo_commits:
            status.repo_commits = repo_commits
        self.updated_at = datetime.now()

    def mark_feature_failed(self, feature_id: str, error_message: str) -> None:
        """Mark a feature as failed."""
        if feature_id not in self.features_status:
            self.features_status[feature_id] = FeatureStatus()
        self.features_status[feature_id].status = "failed"
        self.features_status[feature_id].error_message = error_message
        self.updated_at = datetime.now()

    def increment_test_attempts(self, feature_id: str) -> None:
        """Increment test attempts for a feature."""
        if feature_id not in self.features_status:
            self.features_status[feature_id] = FeatureStatus()
        self.features_status[feature_id].test_attempts += 1
        self.updated_at = datetime.now()

    def get_progress_summary(self) -> str:
        """Get a human-readable progress summary."""
        total = len(self.features_status)
        completed = len(self.get_completed_feature_ids())
        in_progress = self.get_in_progress_feature_id()

        summary = f"Progress: {completed}/{total} features completed"
        if in_progress:
            summary += f", currently working on {in_progress}"
        return summary
