"""Parse project-init.md files into structured configuration."""

import re
from pathlib import Path
from typing import Optional

from ..models.project import ProjectConfig, RepositoryConfig


class ProjectParser:
    """Parser for project-init.md files."""

    def __init__(self, file_path: str):
        """Initialize parser with file path."""
        self.file_path = Path(file_path)
        self.content = ""
        self.sections: dict[str, str] = {}

    def parse(self) -> ProjectConfig:
        """Parse the project-init.md file and return structured config."""
        self.content = self.file_path.read_text()
        self._extract_sections()

        # Determine project type
        project_type = self._determine_project_type()

        # Build config based on type
        config = ProjectConfig(
            title=self._extract_title(),
            introduction=self.sections.get("introduction", ""),
            project_type=project_type,
            jira_ticket=self._extract_jira_ticket(),
            tech_stack=self._extract_tech_stack() if project_type == "new" else None,
            existing_codebase=self._extract_existing_codebase()
            if project_type in ("single_repo", "multi_repo")
            else None,
            current_architecture=self.sections.get("current architecture"),
            repositories=self._extract_repositories()
            if project_type == "multi_repo"
            else [],
            cross_repo_dependencies=self.sections.get("cross-repo dependencies"),
            functional_requirements=self._extract_list_section("functional requirements"),
            system_requirements=self._extract_list_section("system requirements"),
            requirements=self._extract_list_section("requirements"),  # Legacy fallback
            success_criteria=self._extract_list_section("success criteria"),
            testing_instructions=self._extract_list_section("testing instructions"),
            raw_content=self.content,
        )

        return config

    def get_missing_requirements_sections(self) -> list[str]:
        """Check which requirement sections are missing.

        Returns:
            List of missing section names that the user should add
        """
        if not self.sections:
            self._extract_sections()

        missing = []

        # Check for functional requirements
        if not self._extract_list_section("functional requirements"):
            missing.append("Functional Requirements")

        # Check for system requirements
        if not self._extract_list_section("system requirements"):
            missing.append("System Requirements")

        return missing

    def has_legacy_requirements_only(self) -> bool:
        """Check if the file only has the old 'Requirements' section.

        Returns:
            True if using legacy format without functional/system separation
        """
        if not self.sections:
            self._extract_sections()

        has_legacy = bool(self._extract_list_section("requirements"))
        has_functional = bool(self._extract_list_section("functional requirements"))
        has_system = bool(self._extract_list_section("system requirements"))

        return has_legacy and not has_functional and not has_system

    def _extract_sections(self) -> None:
        """Extract all sections from markdown content."""
        # Split by headers (## or ###)
        pattern = r"^(#{2,3})\s+(.+?)$"
        lines = self.content.split("\n")

        current_section = None
        current_content: list[str] = []

        for line in lines:
            match = re.match(pattern, line)
            if match:
                # Save previous section
                if current_section:
                    self.sections[current_section.lower()] = "\n".join(
                        current_content
                    ).strip()

                current_section = match.group(2).strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            self.sections[current_section.lower()] = "\n".join(current_content).strip()

    def _extract_title(self) -> str:
        """Extract the main title (# header)."""
        match = re.search(r"^#\s+(.+?)$", self.content, re.MULTILINE)
        return match.group(1).strip() if match else "Untitled Project"

    def _determine_project_type(self) -> str:
        """Determine project type from content."""
        project_type_section = self.sections.get("project type", "").lower()

        if "multi" in project_type_section:
            return "multi_repo"
        elif "existing" in project_type_section or "single" in project_type_section:
            return "single_repo"
        else:
            return "new"

    def _extract_jira_ticket(self) -> Optional[str]:
        """Extract Jira ticket from content."""
        jira_section = self.sections.get("jira ticket", "")
        if jira_section:
            # Extract just the ticket ID (e.g., PROJ-123)
            match = re.search(r"([A-Z]+-\d+)", jira_section)
            return match.group(1) if match else jira_section.strip()
        return None

    def _extract_tech_stack(self) -> Optional[dict[str, str]]:
        """Extract tech stack for new projects."""
        tech_section = self.sections.get("tech stack", "")
        if not tech_section:
            return None

        stack = {}
        for line in tech_section.split("\n"):
            # Match "- Key: Value" or "- Key - Value"
            match = re.match(r"^-\s*(\w+)[:|-]\s*(.+)$", line.strip())
            if match:
                key = match.group(1).lower()
                value = match.group(2).strip()
                stack[key] = value

        return stack if stack else None

    def _extract_existing_codebase(self) -> Optional[dict[str, str]]:
        """Extract existing codebase info."""
        codebase_section = self.sections.get("existing codebase", "")
        if not codebase_section:
            return None

        info = {}
        for line in codebase_section.split("\n"):
            match = re.match(r"^-\s*(.+?)[:|-]\s*(.+)$", line.strip())
            if match:
                key = match.group(1).lower().strip()
                value = match.group(2).strip()
                info[key] = value

        return info if info else None

    def _extract_repositories(self) -> list[RepositoryConfig]:
        """Extract repository configurations for multi-repo projects."""
        repos = []
        repo_section = self.sections.get("repositories", "")

        if not repo_section:
            # Try to find numbered repository sections in various formats:
            #   "1. Some Repository"       -> r"\d+\.\s+.+repository"
            #   "Repository 1: name (...)"  -> r"repository\s+\d+"
            for key, content in self.sections.items():
                if (
                    re.match(r"\d+\.\s+.+repository", key, re.IGNORECASE)
                    or re.match(r"repository\s+\d+", key, re.IGNORECASE)
                ):
                    repo = self._parse_single_repo_section(key, content)
                    if repo:
                        repos.append(repo)

        return repos

    def _parse_single_repo_section(
        self, name: str, content: str
    ) -> Optional[RepositoryConfig]:
        """Parse a single repository section."""
        info = {"name": name}

        for line in content.split("\n"):
            match = re.match(r"^-\s*(.+?)[:|-]\s*(.+)$", line.strip())
            if match:
                key = match.group(1).lower().strip()
                value = match.group(2).strip()

                if "path" in key:
                    info["path"] = value
                elif "language" in key:
                    info["language"] = value
                elif "framework" in key:
                    info["framework"] = value
                elif "build" in key:
                    info["build_command"] = value
                elif "test" in key:
                    info["test_command"] = value

        if "path" in info and "language" in info:
            return RepositoryConfig(
                name=info.get("name", "unknown"),
                path=info["path"],
                language=info["language"],
                framework=info.get("framework"),
                build_command=info.get("build_command"),
                test_command=info.get("test_command"),
            )

        return None

    def _extract_list_section(self, section_name: str) -> list[str]:
        """Extract a list from a section."""
        content = self.sections.get(section_name, "")
        items = []

        for line in content.split("\n"):
            # Match list items (- item or 1. item)
            match = re.match(r"^(?:-|\d+\.)\s+(.+)$", line.strip())
            if match:
                items.append(match.group(1).strip())

        return items
