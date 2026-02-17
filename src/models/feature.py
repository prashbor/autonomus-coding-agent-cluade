"""Feature and FeatureList Pydantic models."""

from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field


# Feature status type
FeatureStatus = Literal["pending", "in_progress", "completed", "failed"]


class TestingConfig(BaseModel):
    """Testing configuration for a repository."""

    framework: str = Field(description="Test framework (pytest, jest, junit, etc.)")
    command: str = Field(description="Command to run tests")


class CodebaseAnalysis(BaseModel):
    """Analysis of an existing codebase's structure and patterns."""

    # --- Existing fields (unchanged, backward compatible) ---
    structure: dict[str, str] = Field(
        default_factory=dict,
        description="Directory/file structure with descriptions",
    )
    patterns: dict[str, str] = Field(
        default_factory=dict,
        description="Coding patterns and conventions",
    )
    testing: Optional[TestingConfig] = Field(
        default=None,
        description="Testing configuration",
    )

    # --- New fields (all Optional with defaults for backward compat) ---
    architecture_patterns: Optional[list[str]] = Field(
        default=None,
        description="Architectural patterns found, e.g. 'layered architecture with repository pattern'",
    )
    coding_conventions: Optional[dict[str, str]] = Field(
        default=None,
        description="Coding conventions with actual code examples from the codebase",
    )
    key_abstractions: Optional[list[dict[str, str]]] = Field(
        default=None,
        description="Key classes/interfaces/patterns, each with 'name', 'type', 'purpose', 'file'",
    )
    module_relationships: Optional[list[dict[str, str]]] = Field(
        default=None,
        description="Module dependency relationships, each with 'from', 'to', 'relationship'",
    )
    api_patterns: Optional[dict[str, str]] = Field(
        default=None,
        description="API patterns found, e.g. {'style': 'REST', 'auth': 'Bearer token middleware'}",
    )
    entry_points: Optional[list[str]] = Field(
        default=None,
        description="Main entry point files identified by the agent",
    )
    analysis_method: Optional[str] = Field(
        default=None,
        description="How the analysis was performed: 'agent' or 'deterministic'",
    )


class Repository(BaseModel):
    """Repository configuration for multi-repo projects."""

    id: str = Field(description="Unique identifier for the repository")
    path: str = Field(description="Absolute path to the repository")
    language: str = Field(description="Primary programming language")
    framework: Optional[str] = Field(
        default=None,
        description="Framework used (spring-boot, fastapi, react, etc.)",
    )
    dialect: Optional[str] = Field(
        default=None,
        description="Language dialect (postgresql, mysql, etc.)",
    )
    codebase_analysis: Optional[CodebaseAnalysis] = Field(
        default=None,
        description="Analysis of existing codebase",
    )


class RepoTask(BaseModel):
    """A task to be performed in a specific repository."""

    repo_id: str = Field(description="ID of the target repository")
    description: str = Field(description="Description of what to do in this repo")
    files: list[str] = Field(
        default_factory=list,
        description="Expected files to create/modify",
    )
    test_command: Optional[str] = Field(
        default=None,
        description="Command to run tests for this task",
    )


class Feature(BaseModel):
    """A feature to be implemented."""

    id: str = Field(description="Unique feature ID (e.g., FEAT-001)")
    name: str = Field(description="Short name of the feature")
    description: str = Field(description="Detailed description of the feature")
    status: FeatureStatus = Field(
        default="pending",
        description="Feature status: pending, in_progress, or completed",
    )
    priority: int = Field(default=1, description="Priority (1 = highest)")
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of feature IDs this feature depends on",
    )
    repo_tasks: list[RepoTask] = Field(
        default_factory=list,
        description="Tasks for each repository (multi-repo support)",
    )
    requires_tests: bool = Field(
        default=True,
        description="Whether this feature requires tests",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria that must be met for feature completion",
    )
    test_criteria: list[str] = Field(
        default_factory=list,
        description="Specific test cases to implement",
    )

    # New fields for comprehensive testing and PR management
    test_suites: List[str] = Field(
        default_factory=list,
        description="List of test suite names generated for this feature",
    )
    pr_group_id: Optional[str] = Field(
        default=None,
        description="ID of PR group this feature belongs to",
    )
    commit_hash: Optional[str] = Field(
        default=None,
        description="Git commit hash when this feature was implemented",
    )


class RepoDependency(BaseModel):
    """Dependency between repositories."""

    upstream: str = Field(description="ID of upstream repository")
    downstream: str = Field(description="ID of downstream repository")


class TechStack(BaseModel):
    """Technology stack for new projects."""

    language: str = Field(description="Primary programming language")
    framework: Optional[str] = Field(default=None, description="Framework to use")
    database: Optional[str] = Field(default=None, description="Database to use")


class FeatureList(BaseModel):
    """Complete feature list generated from project-init.md."""

    project_name: str = Field(description="Name of the project")
    description: str = Field(description="Project description")
    project_type: str = Field(
        description="Type: 'new', 'single_repo', or 'multi_repo'"
    )
    jira_ticket: Optional[str] = Field(
        default=None,
        description="Jira ticket for branch naming (existing repos)",
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Generated branch name",
    )
    tech_stack: Optional[TechStack] = Field(
        default=None,
        description="Tech stack (for new projects)",
    )
    output_directory: Optional[str] = Field(
        default=None,
        description="Output directory (for new projects)",
    )
    repositories: list[Repository] = Field(
        default_factory=list,
        description="List of repositories (for existing repo projects)",
    )
    repo_dependencies: list[RepoDependency] = Field(
        default_factory=list,
        description="Dependencies between repositories",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="List of features to implement",
    )
    testing_strategy: Optional[dict] = Field(
        default=None,
        description="Auto-generated testing strategy with framework, commands, and commit policy",
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the feature list was generated",
    )

    def get_pending_features(self, completed_ids: Optional[set[str]] = None) -> list[Feature]:
        """Get features that are ready to be implemented.

        Excludes completed and failed features.

        Args:
            completed_ids: Optional set of completed IDs (for backward compatibility).
                          If not provided, uses feature.status field.
        """
        # Build completed set from status if not provided
        if completed_ids is None:
            completed_ids = {f.id for f in self.features if f.status == "completed"}

        # Also exclude failed features
        skip_ids = completed_ids | {f.id for f in self.features if f.status == "failed"}

        pending = []
        for feature in self.features:
            if feature.status in ("completed", "failed") or feature.id in skip_ids:
                continue
            # Check if all dependencies are completed
            if all(dep in completed_ids for dep in feature.depends_on):
                pending.append(feature)
        return pending

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID."""
        for feature in self.features:
            if feature.id == feature_id:
                return feature
        return None

    def update_feature_status(self, feature_id: str, status: FeatureStatus) -> bool:
        """Update a feature's status.

        Args:
            feature_id: ID of the feature to update
            status: New status value

        Returns:
            True if feature was found and updated
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = status
                return True
        return False

    def get_features_by_status(self, status: FeatureStatus) -> list[Feature]:
        """Get all features with a specific status."""
        return [f for f in self.features if f.status == status]

    def get_completed_feature_ids(self) -> set[str]:
        """Get IDs of all completed features."""
        return {f.id for f in self.features if f.status == "completed"}

    def get_completed_features(self) -> list[Feature]:
        """Get all completed features."""
        return [f for f in self.features if f.status == "completed"]

    def get_failed_features(self) -> list[Feature]:
        """Get all features that failed validation."""
        return [f for f in self.features if f.status == "failed"]

    def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get a repository by ID."""
        for repo in self.repositories:
            if repo.id == repo_id:
                return repo
        return None
