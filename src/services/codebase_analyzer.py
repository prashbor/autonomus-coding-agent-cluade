"""Analyze existing codebases using AI agent with deterministic fallback."""

import json
import os
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..models.feature import CodebaseAnalysis, TestingConfig
from ..agent.session import AgentSession
from ..agent.tools import READONLY_TOOL_DEFINITIONS, ReadOnlyToolExecutor
from ..config import analysis_config

if TYPE_CHECKING:
    from ..services.cost_tracker import CostTracker


class CodebaseAnalyzer:
    """Analyzes existing codebases to extract structure and patterns.

    Two-phase approach:
    1. Deterministic: Fast file tree collection (no API call)
    2. Agent: Claude explores codebase with read-only tools (bounded turns)

    Falls back to deterministic-only if agent fails.
    """

    # Common patterns for different languages
    LANGUAGE_PATTERNS = {
        "python": {
            "extensions": [".py"],
            "test_frameworks": ["pytest", "unittest"],
            "test_patterns": ["test_*.py", "*_test.py"],
            "naming": "snake_case",
        },
        "java": {
            "extensions": [".java"],
            "test_frameworks": ["junit", "testng"],
            "test_patterns": ["*Test.java", "*Tests.java"],
            "naming": "PascalCase for classes, camelCase for methods",
        },
        "typescript": {
            "extensions": [".ts", ".tsx"],
            "test_frameworks": ["jest", "mocha", "vitest"],
            "test_patterns": ["*.test.ts", "*.spec.ts"],
            "naming": "camelCase for functions, PascalCase for components",
        },
        "javascript": {
            "extensions": [".js", ".jsx"],
            "test_frameworks": ["jest", "mocha"],
            "test_patterns": ["*.test.js", "*.spec.js"],
            "naming": "camelCase",
        },
        "sql": {
            "extensions": [".sql"],
            "test_frameworks": ["pgTAP"],
            "test_patterns": ["test_*.sql"],
            "naming": "snake_case",
        },
    }

    # Directories to ignore
    IGNORE_DIRS = {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
        "target",
        "build",
        "dist",
        ".next",
        "coverage",
    }

    def __init__(self, repo_path: str, cost_tracker: Optional["CostTracker"] = None):
        """Initialize analyzer with repository path.

        Args:
            repo_path: Path to the repository to analyze
            cost_tracker: Optional CostTracker for recording API costs
        """
        self.repo_path = Path(repo_path)
        self._cost_tracker = cost_tracker

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def analyze(self) -> CodebaseAnalysis:
        """Perform full analysis: deterministic + agent with fallback.

        Returns CodebaseAnalysis with enriched fields if agent succeeds,
        or basic deterministic analysis if agent fails.
        """
        # Phase 1: Deterministic file tree (fast, no API)
        file_tree = self._collect_file_tree()
        deterministic_result = self._deterministic_analysis()

        # Phase 2: Agent-based deep analysis
        try:
            agent_result = await self._agent_analysis(file_tree)
            return self._merge_results(deterministic_result, agent_result)
        except Exception as e:
            print(f"   Warning: Agent analysis failed ({e}), using deterministic fallback")
            deterministic_result.analysis_method = "deterministic"
            return deterministic_result

    def analyze_sync(self) -> CodebaseAnalysis:
        """Synchronous fallback - deterministic only.

        For use when agent analysis is disabled or caller cannot await.
        """
        result = self._deterministic_analysis()
        result.analysis_method = "deterministic"
        return result

    # -------------------------------------------------------------------------
    # Agent-based analysis
    # -------------------------------------------------------------------------

    async def _agent_analysis(self, file_tree: str) -> CodebaseAnalysis:
        """Run AI agent analysis session with read-only tools.

        Creates a bounded AgentSession that explores the codebase,
        then parses the structured JSON output.
        """
        system_prompt = self._build_analysis_system_prompt()
        user_prompt = self._build_analysis_user_prompt(file_tree)

        session = AgentSession(
            working_directory=str(self.repo_path),
            system_prompt=system_prompt,
            max_turns=analysis_config.max_turns,
            model_id=analysis_config.model_id,
            tool_definitions=READONLY_TOOL_DEFINITIONS,
            tool_executor=ReadOnlyToolExecutor(str(self.repo_path)),
            cost_tracker=self._cost_tracker,
            cost_phase="plan",
            cost_label_prefix="codebase_analysis",
        )

        result = await session.send_message(user_prompt)

        if not result.success:
            raise RuntimeError(f"Agent session failed: {result.error}")

        return self._parse_agent_response(result.content)

    def _build_analysis_system_prompt(self) -> str:
        """System prompt for the codebase analysis agent."""
        return """You are an expert software architect analyzing an existing codebase. Your goal is to understand the architecture, patterns, conventions, and structure of this project.

## Your Tools
You have two read-only tools:
- **read_file**: Read the contents of any file
- **list_directory**: List contents of any directory

## Your Approach
1. Start by examining the file tree provided in the user message
2. Read key configuration files (package.json, pyproject.toml, pom.xml, requirements.txt, etc.)
3. Read entry points and main application files
4. Read a few representative source files to understand patterns
5. Look at test files to understand testing approach
6. Examine any architecture-related files (README, docs)

## Budget
You have a LIMITED number of tool calls. Be strategic:
- Prioritize configuration files and entry points first
- Read 2-3 representative source files, not every file
- Focus on understanding patterns, not memorizing code

## Output Format
After exploration, you MUST output your analysis as a JSON block wrapped in ```json ... ``` markers. The JSON must conform to this exact schema:

```json
{
  "structure": {"directory_or_file": "description", ...},
  "patterns": {"pattern_name": "pattern_value", ...},
  "testing": {"framework": "pytest/jest/junit/etc", "command": "test command"} or null,
  "architecture_patterns": ["pattern description 1", "pattern description 2"],
  "coding_conventions": {"convention_name": "description with actual examples from code"},
  "key_abstractions": [
    {"name": "ClassName", "type": "class", "purpose": "what it does", "file": "path/to/file.py"}
  ],
  "module_relationships": [
    {"from": "module_a", "to": "module_b", "relationship": "imports"}
  ],
  "api_patterns": {"style": "REST/GraphQL/RPC", "auth": "description", ...} or null,
  "entry_points": ["main.py", "src/index.ts"]
}
```

Be specific and concrete. Reference actual file names, class names, and code patterns you observed. Set any field to null or empty if not applicable."""

    def _build_analysis_user_prompt(self, file_tree: str) -> str:
        """User prompt with the file tree for initial orientation."""
        return f"""Analyze the codebase at this location. Here is the file tree to orient you:

```
{file_tree}
```

Explore the codebase using read_file and list_directory tools. Focus on understanding:
1. Overall architecture and design patterns
2. Coding conventions (naming, error handling, imports, etc.)
3. Key abstractions (important classes, interfaces, base classes)
4. How modules relate to each other
5. API patterns (if any)
6. Testing setup and approach
7. Entry points

After exploration, output your complete analysis as a JSON block. Be thorough but efficient with your tool calls."""

    def _parse_agent_response(self, response: str) -> CodebaseAnalysis:
        """Extract structured CodebaseAnalysis from agent's final text response.

        Parses JSON from markdown code block, validates through Pydantic model
        construction. If the agent returns invalid types, Pydantic raises
        ValidationError which propagates to the try/except in analyze().
        """
        # Try to find JSON in markdown code block
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            brace_match = re.search(r"\{.*\}", response, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0)
            else:
                raise ValueError("No JSON found in agent response")

        data = json.loads(json_str)

        # Build TestingConfig explicitly from nested dict (not raw passthrough)
        testing = None
        if data.get("testing") and isinstance(data["testing"], dict):
            testing = TestingConfig(
                framework=data["testing"].get("framework", "unknown"),
                command=data["testing"].get("command", ""),
            )

        # Construct through Pydantic model - triggers validation
        return CodebaseAnalysis(
            structure=data.get("structure", {}),
            patterns=data.get("patterns", {}),
            testing=testing,
            architecture_patterns=data.get("architecture_patterns"),
            coding_conventions=data.get("coding_conventions"),
            key_abstractions=data.get("key_abstractions"),
            module_relationships=data.get("module_relationships"),
            api_patterns=data.get("api_patterns"),
            entry_points=data.get("entry_points"),
            analysis_method="agent",
        )

    def _merge_results(
        self, deterministic: CodebaseAnalysis, agent: CodebaseAnalysis
    ) -> CodebaseAnalysis:
        """Merge agent results with deterministic results.

        Agent results take precedence for overlapping fields.
        Deterministic results fill in any gaps the agent missed.
        """
        # For structure: merge both dicts, agent values win on conflict
        merged_structure = {**deterministic.structure, **agent.structure}

        # For patterns: merge both dicts, agent values win on conflict
        merged_patterns = {**deterministic.patterns, **agent.patterns}

        # For testing: prefer agent detection, fall back to deterministic
        merged_testing = agent.testing or deterministic.testing

        return CodebaseAnalysis(
            structure=merged_structure,
            patterns=merged_patterns,
            testing=merged_testing,
            architecture_patterns=agent.architecture_patterns,
            coding_conventions=agent.coding_conventions,
            key_abstractions=agent.key_abstractions,
            module_relationships=agent.module_relationships,
            api_patterns=agent.api_patterns,
            entry_points=agent.entry_points,
            analysis_method="agent",
        )

    # -------------------------------------------------------------------------
    # File tree collection (deterministic, no API call)
    # -------------------------------------------------------------------------

    def _collect_file_tree(self, max_depth: Optional[int] = None) -> str:
        """Collect file tree as a string for the agent's initial context.

        Bounded to max_depth levels to avoid overwhelming the context.
        """
        if max_depth is None:
            max_depth = analysis_config.max_tree_depth
        lines: list[str] = []
        self._walk_tree(self.repo_path, lines, prefix="", depth=0, max_depth=max_depth)
        return "\n".join(lines)

    def _walk_tree(
        self, path: Path, lines: list[str], prefix: str, depth: int, max_depth: int
    ) -> None:
        """Recursively build tree representation."""
        if depth > max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        # Filter ignored directories and hidden dirs
        entries = [
            e
            for e in entries
            if e.name not in self.IGNORE_DIRS
            and not (e.name.startswith(".") and e.is_dir())
        ]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk_tree(
                    entry, lines, prefix + extension, depth + 1, max_depth
                )

    # -------------------------------------------------------------------------
    # Deterministic analysis (preserved from original implementation)
    # -------------------------------------------------------------------------

    def _deterministic_analysis(self) -> CodebaseAnalysis:
        """Run the existing deterministic analysis (all original logic)."""
        structure = self._analyze_structure()
        patterns = self._analyze_patterns()
        testing = self._detect_testing_config()

        return CodebaseAnalysis(
            structure=structure,
            patterns=patterns,
            testing=testing,
        )

    def _analyze_structure(self) -> dict[str, str]:
        """Analyze directory structure and identify key paths."""
        structure = {}

        for item in self.repo_path.iterdir():
            if item.name.startswith(".") and item.name not in [".env.example"]:
                continue
            if item.name in self.IGNORE_DIRS:
                continue

            if item.is_dir():
                description = self._describe_directory(item)
                structure[f"{item.name}/"] = description
            elif item.is_file():
                description = self._describe_file(item)
                if description:
                    structure[item.name] = description

        return structure

    def _describe_directory(self, dir_path: Path) -> str:
        """Generate description for a directory based on its contents."""
        name = dir_path.name.lower()

        # Common directory purposes
        descriptions = {
            "src": "Main source code",
            "lib": "Library/utility code",
            "tests": "Test files",
            "test": "Test files",
            "docs": "Documentation",
            "config": "Configuration files",
            "scripts": "Utility scripts",
            "migrations": "Database migrations",
            "models": "Data models",
            "controllers": "Request handlers/controllers",
            "services": "Business logic services",
            "api": "API endpoints",
            "components": "UI components",
            "hooks": "Custom hooks",
            "utils": "Utility functions",
            "helpers": "Helper functions",
            "types": "Type definitions",
            "interfaces": "Interface definitions",
            "repositories": "Data access layer",
            "entities": "Entity definitions",
        }

        if name in descriptions:
            return descriptions[name]

        # Analyze contents for better description
        files = list(dir_path.glob("*"))
        if not files:
            return "Empty directory"

        # Count file types
        extensions = {}
        for f in files:
            if f.is_file():
                ext = f.suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1

        if ".py" in extensions:
            return "Python modules"
        elif ".java" in extensions:
            return "Java source files"
        elif ".ts" in extensions or ".tsx" in extensions:
            return "TypeScript files"
        elif ".sql" in extensions:
            return "SQL files"

        return f"Contains {len(files)} items"

    def _describe_file(self, file_path: Path) -> Optional[str]:
        """Generate description for important files."""
        name = file_path.name.lower()

        important_files = {
            "main.py": "Python application entry point",
            "app.py": "Application entry point",
            "__main__.py": "Package entry point",
            "index.ts": "TypeScript entry point",
            "index.js": "JavaScript entry point",
            "app.ts": "Application entry point",
            "app.js": "Application entry point",
            "main.java": "Java main class",
            "application.java": "Spring Boot application",
            "pom.xml": "Maven configuration",
            "build.gradle": "Gradle configuration",
            "package.json": "Node.js package configuration",
            "requirements.txt": "Python dependencies",
            "pyproject.toml": "Python project configuration",
            "setup.py": "Python package setup",
            "dockerfile": "Docker configuration",
            "docker-compose.yml": "Docker Compose configuration",
            "makefile": "Build automation",
            ".env.example": "Environment variables template",
            "readme.md": "Project documentation",
        }

        return important_files.get(name)

    def _analyze_patterns(self) -> dict[str, str]:
        """Analyze coding patterns and conventions."""
        patterns = {}

        # Detect language
        language = self._detect_primary_language()
        if language:
            patterns["language"] = language
            lang_info = self.LANGUAGE_PATTERNS.get(language, {})
            if "naming" in lang_info:
                patterns["naming"] = lang_info["naming"]

        # Detect framework
        framework = self._detect_framework()
        if framework:
            patterns["framework"] = framework

        # Detect project structure pattern
        structure_pattern = self._detect_structure_pattern()
        if structure_pattern:
            patterns["structure"] = structure_pattern

        return patterns

    def _detect_primary_language(self) -> Optional[str]:
        """Detect the primary programming language."""
        extension_counts: dict[str, int] = {}

        for root, dirs, files in os.walk(self.repo_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext:
                    extension_counts[ext] = extension_counts.get(ext, 0) + 1

        # Map extensions to languages
        ext_to_lang = {
            ".py": "python",
            ".java": "java",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".sql": "sql",
        }

        # Find most common language
        lang_counts: dict[str, int] = {}
        for ext, count in extension_counts.items():
            if ext in ext_to_lang:
                lang = ext_to_lang[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + count

        if lang_counts:
            return max(lang_counts, key=lang_counts.get)  # type: ignore

        return None

    def _detect_framework(self) -> Optional[str]:
        """Detect the framework being used."""
        # Check for Python frameworks
        requirements_file = self.repo_path / "requirements.txt"
        if requirements_file.exists():
            content = requirements_file.read_text().lower()
            if "fastapi" in content:
                return "FastAPI"
            elif "django" in content:
                return "Django"
            elif "flask" in content:
                return "Flask"

        # Check for Node.js frameworks
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            content = package_json.read_text().lower()
            if "react" in content:
                return "React"
            elif "vue" in content:
                return "Vue"
            elif "angular" in content:
                return "Angular"
            elif "express" in content:
                return "Express"
            elif "next" in content:
                return "Next.js"

        # Check for Java frameworks
        pom_xml = self.repo_path / "pom.xml"
        if pom_xml.exists():
            content = pom_xml.read_text().lower()
            if "spring-boot" in content:
                return "Spring Boot"

        return None

    def _detect_structure_pattern(self) -> Optional[str]:
        """Detect the project structure pattern."""
        dirs = {d.name for d in self.repo_path.iterdir() if d.is_dir()}

        if "src" in dirs and "tests" in dirs:
            return "src/tests layout"
        elif "app" in dirs and "tests" in dirs:
            return "app/tests layout"
        elif "lib" in dirs:
            return "lib layout"
        elif "src" in dirs:
            if (self.repo_path / "src" / "main").exists():
                return "Maven standard layout"
            return "src layout"

        return None

    def _detect_testing_config(self) -> Optional[TestingConfig]:
        """Detect testing configuration."""
        # Check for Python testing
        if (self.repo_path / "pytest.ini").exists() or (
            self.repo_path / "pyproject.toml"
        ).exists():
            return TestingConfig(framework="pytest", command="pytest")

        if (self.repo_path / "tests").exists() or (self.repo_path / "test").exists():
            # Check for conftest.py (pytest)
            if list(self.repo_path.rglob("conftest.py")):
                return TestingConfig(framework="pytest", command="pytest")

        # Check for Node.js testing
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            content = package_json.read_text().lower()
            if "jest" in content:
                return TestingConfig(framework="Jest", command="npm test")
            elif "mocha" in content:
                return TestingConfig(framework="Mocha", command="npm test")
            elif "vitest" in content:
                return TestingConfig(framework="Vitest", command="npm test")

        # Check for Java testing
        pom_xml = self.repo_path / "pom.xml"
        if pom_xml.exists():
            return TestingConfig(framework="JUnit", command="mvn test")

        build_gradle = self.repo_path / "build.gradle"
        if build_gradle.exists():
            return TestingConfig(framework="JUnit", command="gradle test")

        return None

    def get_key_files(self, max_files: int = 10) -> list[str]:
        """Get list of key files to understand the codebase."""
        key_files = []

        # Priority files
        priority_patterns = [
            "main.py",
            "app.py",
            "index.ts",
            "index.js",
            "Application.java",
            "pom.xml",
            "package.json",
            "requirements.txt",
            "README.md",
        ]

        for pattern in priority_patterns:
            matches = list(self.repo_path.rglob(pattern))
            for match in matches[:2]:  # Max 2 per pattern
                rel_path = str(match.relative_to(self.repo_path))
                if rel_path not in key_files:
                    key_files.append(rel_path)

        return key_files[:max_files]
