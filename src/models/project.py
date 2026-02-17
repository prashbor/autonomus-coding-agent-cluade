"""Project configuration models parsed from project-init.md."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class RepositoryConfig(BaseModel):
    """Repository configuration from project-init.md."""

    name: str = Field(description="Repository name")
    path: str = Field(description="Path to the repository")
    language: str = Field(description="Primary programming language")
    framework: Optional[str] = Field(default=None, description="Framework used")
    build_command: Optional[str] = Field(default=None, description="Build command")
    test_command: Optional[str] = Field(default=None, description="Test command")
    key_paths: list[str] = Field(
        default_factory=list,
        description="Key paths/modules to understand",
    )


class ProjectConfig(BaseModel):
    """Parsed configuration from project-init.md."""

    title: str = Field(description="Project title")
    introduction: str = Field(description="Project introduction/description")
    project_type: Literal["new", "single_repo", "multi_repo"] = Field(
        description="Type of project"
    )
    jira_ticket: Optional[str] = Field(
        default=None,
        description="Jira ticket for existing repos",
    )

    # For new projects
    tech_stack: Optional[dict[str, str]] = Field(
        default=None,
        description="Technology stack (language, framework, database)",
    )

    # For existing repos
    existing_codebase: Optional[dict[str, str]] = Field(
        default=None,
        description="Existing codebase info (path, main entry, etc.)",
    )
    current_architecture: Optional[str] = Field(
        default=None,
        description="Description of current architecture",
    )

    # For multi-repo
    repositories: list[RepositoryConfig] = Field(
        default_factory=list,
        description="List of repositories for multi-repo projects",
    )
    cross_repo_dependencies: Optional[str] = Field(
        default=None,
        description="Description of cross-repo dependencies",
    )

    # Common fields
    functional_requirements: list[str] = Field(
        default_factory=list,
        description="List of functional requirements (what the system should DO)",
    )
    system_requirements: list[str] = Field(
        default_factory=list,
        description="List of system/non-functional requirements (performance, security, etc.)",
    )
    requirements: list[str] = Field(
        default_factory=list,
        description="Legacy: combined list of requirements (deprecated, use functional/system)",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Success criteria",
    )
    testing_instructions: list[str] = Field(
        default_factory=list,
        description="Testing instructions",
    )

    # Raw content for Claude processing
    raw_content: str = Field(
        default="",
        description="Raw markdown content",
    )
