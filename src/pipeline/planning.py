"""Planning pipeline - generates feature list from project description."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..models.project import ProjectConfig, RepositoryConfig
from ..models.feature import FeatureList, CodebaseAnalysis
from ..services.project_parser import ProjectParser
from ..services.codebase_analyzer import CodebaseAnalyzer
from ..services.feature_generator import FeatureGenerator
from ..services.spec_enhancer import SpecEnhancer

if TYPE_CHECKING:
    from ..services.cost_tracker import CostTracker


class MissingRequirementsError(Exception):
    """Raised when required sections are missing from project-init.md."""

    def __init__(self, missing_sections: list[str], file_path: str):
        self.missing_sections = missing_sections
        self.file_path = file_path
        sections_str = ", ".join(missing_sections)
        super().__init__(
            f"Missing required sections in {file_path}: {sections_str}"
        )


class PlanningPipeline:
    """Orchestrates the planning phase to generate feature_list.json."""

    def __init__(
        self,
        project_init_path: str,
        output_dir: Optional[str] = None,
        repo_path: Optional[str] = None,
        multi_repo: bool = False,
        cost_tracker: Optional["CostTracker"] = None,
    ):
        """Initialize planning pipeline.

        Args:
            project_init_path: Path to project-init.md
            output_dir: Output directory for new projects
            repo_path: Path to existing repo (single repo mode)
            multi_repo: Whether this is a multi-repo project
            cost_tracker: Optional CostTracker for recording API costs
        """
        self.project_init_path = Path(project_init_path)
        self.output_dir = output_dir
        self.repo_path = repo_path
        self.multi_repo = multi_repo
        self._cost_tracker = cost_tracker

        self.project_config: Optional[ProjectConfig] = None
        self.codebase_analyses: dict[str, CodebaseAnalysis] = {}
        self._parser: Optional[ProjectParser] = None

    def parse_project(self) -> ProjectConfig:
        """Parse the project-init.md file."""
        self._parser = ProjectParser(str(self.project_init_path))
        self.project_config = self._parser.parse()

        # Override project type if specified via CLI
        if self.multi_repo:
            self.project_config.project_type = "multi_repo"
        elif self.repo_path:
            self.project_config.project_type = "single_repo"
            # Add repo path to config
            if not self.project_config.existing_codebase:
                self.project_config.existing_codebase = {}
            self.project_config.existing_codebase["path"] = self.repo_path

        return self.project_config

    def validate_requirements(self) -> list[str]:
        """Validate that required sections are present.

        Returns:
            List of missing section names (empty if all present)
        """
        if not self._parser:
            raise ValueError("Must call parse_project() first")

        return self._parser.get_missing_requirements_sections()

    def prompt_for_missing_requirements(self, interactive: bool = True) -> bool:
        """Prompt user to add missing requirement sections.

        Args:
            interactive: If True, prompt user interactively. If False, just print message.

        Returns:
            True if requirements are complete, False if still missing
        """
        missing = self.validate_requirements()

        if not missing:
            return True

        # Check if using legacy format
        if self._parser and self._parser.has_legacy_requirements_only():
            print(f"\n{'='*60}")
            print("NOTICE: Legacy Requirements Format Detected")
            print(f"{'='*60}")
            print(f"Your project-init.md uses the old 'Requirements' section format.")
            print(f"Please update to use separate sections:\n")
            print("  ## Functional Requirements")
            print("  What the system should DO (user-facing features and behaviors):")
            print("  - FR-1: [User can do X / System provides Y]")
            print("  - FR-2: ...")
            print()
            print("  ## System Requirements")
            print("  Non-functional requirements (performance, security, etc.):")
            print("  - SR-1: [Performance / Security / Scalability requirement]")
            print("  - SR-2: ...")
            print(f"\n{'='*60}")
        else:
            print(f"\n{'='*60}")
            print("MISSING REQUIRED SECTIONS")
            print(f"{'='*60}")
            print(f"The following sections are missing from {self.project_init_path}:\n")
            for section in missing:
                print(f"  - {section}")
            print()

        if interactive:
            print("Please add the missing sections to your project-init.md file.")
            print()
            response = input("Press Enter after updating the file (or 'q' to quit): ").strip()

            if response.lower() == 'q':
                return False

            # Re-parse the file
            self._parser = ProjectParser(str(self.project_init_path))
            self.project_config = self._parser.parse()

            # Check again
            still_missing = self.validate_requirements()
            if still_missing:
                print(f"\nStill missing: {', '.join(still_missing)}")
                return self.prompt_for_missing_requirements(interactive=True)

            print("Requirements sections validated successfully!")
            return True
        else:
            raise MissingRequirementsError(missing, str(self.project_init_path))

    async def analyze_codebases(self) -> dict[str, CodebaseAnalysis]:
        """Analyze existing codebases if working with existing repos.

        Uses AI-agent-based analysis by default (configurable via
        ANALYSIS_USE_AGENT env var). Falls back to deterministic if
        agent analysis fails.
        """
        if not self.project_config:
            raise ValueError("Must call parse_project() first")

        if self.project_config.project_type == "new":
            return {}

        from ..config import analysis_config

        if self.project_config.project_type == "single_repo":
            repo_path = self.repo_path or (
                self.project_config.existing_codebase.get("path")
                if self.project_config.existing_codebase
                else None
            )

            if repo_path:
                analyzer = CodebaseAnalyzer(repo_path, cost_tracker=self._cost_tracker)
                if analysis_config.use_agent:
                    self.codebase_analyses["main"] = await analyzer.analyze()
                else:
                    self.codebase_analyses["main"] = analyzer.analyze_sync()
                method = self.codebase_analyses["main"].analysis_method or "deterministic"
                print(f"   Analyzed codebase at: {repo_path} (method: {method})")

        elif self.project_config.project_type == "multi_repo":
            for repo_config in self.project_config.repositories:
                analyzer = CodebaseAnalyzer(repo_config.path, cost_tracker=self._cost_tracker)
                if analysis_config.use_agent:
                    self.codebase_analyses[repo_config.name] = await analyzer.analyze()
                else:
                    self.codebase_analyses[repo_config.name] = analyzer.analyze_sync()
                method = self.codebase_analyses[repo_config.name].analysis_method or "deterministic"
                print(f"   Analyzed codebase: {repo_config.name} at {repo_config.path} (method: {method})")

        return self.codebase_analyses

    async def generate_features(self) -> FeatureList:
        """Generate feature list using Claude."""
        if not self.project_config:
            raise ValueError("Must call parse_project() first")

        generator = FeatureGenerator(self.project_config, cost_tracker=self._cost_tracker)

        # Generate testing strategy
        testing_strategy = self._generate_testing_strategy()

        feature_list = await generator.generate(
            codebase_analyses=self.codebase_analyses if self.codebase_analyses else None,
            output_dir=self.output_dir,
            testing_strategy=testing_strategy,
        )

        return feature_list

    def _generate_testing_strategy(self) -> dict:
        """Generate testing strategy based on project type and codebase analysis.

        Returns:
            Dict with testing strategy info
        """
        if not self.project_config:
            return {"strategy": "unknown", "details": "Project not parsed yet"}

        project_type = self.project_config.project_type

        if project_type == "new":
            # Generate testing strategy based on tech stack
            tech_stack = self.project_config.tech_stack or {}
            language = tech_stack.get("language", "python").lower()
            framework = tech_stack.get("framework", "").lower()

            strategy = {
                "strategy": "auto_generated",
                "source": "tech_stack",
                "commit_tests": True,
            }

            if "python" in language:
                strategy["framework"] = "pytest"
                strategy["command"] = "pytest tests/ -v"
                strategy["coverage_command"] = "pytest tests/ -v --cov=src --cov-report=term-missing"
                strategy["details"] = "Using pytest for Python testing with coverage reporting"
            elif "typescript" in language or "javascript" in language:
                if "react" in framework or "vue" in framework or "angular" in framework:
                    strategy["framework"] = "jest + testing-library"
                    strategy["command"] = "npm test"
                    strategy["coverage_command"] = "npm test -- --coverage"
                else:
                    strategy["framework"] = "jest"
                    strategy["command"] = "npm test"
                    strategy["coverage_command"] = "npm test -- --coverage"
                strategy["details"] = "Using Jest for JavaScript/TypeScript testing"
            elif "java" in language:
                strategy["framework"] = "JUnit 5"
                strategy["command"] = "mvn test"
                strategy["coverage_command"] = "mvn test jacoco:report"
                strategy["details"] = "Using JUnit 5 for Java testing with Jacoco coverage"
            elif "go" in language:
                strategy["framework"] = "go test"
                strategy["command"] = "go test ./..."
                strategy["coverage_command"] = "go test ./... -cover"
                strategy["details"] = "Using Go's built-in testing framework"
            else:
                strategy["framework"] = "unknown"
                strategy["command"] = "# Configure test command for your language"
                strategy["details"] = f"Please configure testing for {language}"

            return strategy

        elif project_type in ("single_repo", "multi_repo"):
            # Use detected testing from codebase analysis
            strategies = {}

            for repo_id, analysis in self.codebase_analyses.items():
                if analysis.testing:
                    strategies[repo_id] = {
                        "strategy": "detected",
                        "source": "codebase_analysis",
                        "framework": analysis.testing.framework,
                        "command": analysis.testing.command,
                        "commit_tests": True,
                        "details": f"Detected {analysis.testing.framework} in existing codebase",
                    }
                else:
                    strategies[repo_id] = {
                        "strategy": "not_detected",
                        "source": "codebase_analysis",
                        "framework": "unknown",
                        "command": "# No testing detected in repository",
                        "commit_tests": False,
                        "details": "No testing framework detected. Tests will run locally but NOT be committed.",
                        "warning": "Tests for new functionality will be validated locally but not committed to the feature branch.",
                    }

            if len(strategies) == 1:
                return list(strategies.values())[0]
            return {"strategy": "multi_repo", "repositories": strategies}

        return {"strategy": "unknown", "details": "Unknown project type"}

    def _save_codebase_analysis_cache(self) -> Optional[str]:
        """Save codebase analysis results to a JSON cache file.

        Persists analysis alongside the project-init file so the Feature phase
        can load it instead of re-running expensive analysis.

        Returns:
            Path to saved file, or None if no analyses to save.
        """
        if not self.codebase_analyses or not self.project_config:
            return None

        from ..utils.file_naming import generate_analysis_filename

        repos_data: dict = {}

        if self.project_config.project_type == "single_repo":
            analysis = self.codebase_analyses.get("main")
            if analysis:
                repo_path = self.repo_path or (
                    self.project_config.existing_codebase.get("path", "")
                    if self.project_config.existing_codebase
                    else ""
                )
                # Best-effort language detection for single repo
                language = "unknown"
                if self.project_config.tech_stack:
                    language = self.project_config.tech_stack.get("language", "unknown")
                elif self.project_config.existing_codebase:
                    language = self.project_config.existing_codebase.get("language", "unknown")
                elif analysis.patterns:
                    language = analysis.patterns.get("language", "unknown")

                repos_data["main"] = {
                    "path": repo_path,
                    "language": language,
                    "framework": None,
                    "build_command": None,
                    "test_command": None,
                    "analysis": analysis.model_dump(mode="json"),
                }

        elif self.project_config.project_type == "multi_repo":
            for repo_config in self.project_config.repositories:
                analysis = self.codebase_analyses.get(repo_config.name)
                if analysis:
                    repos_data[repo_config.name] = {
                        "path": repo_config.path,
                        "language": repo_config.language,
                        "framework": repo_config.framework,
                        "build_command": repo_config.build_command,
                        "test_command": repo_config.test_command,
                        "analysis": analysis.model_dump(mode="json"),
                    }

        if not repos_data:
            return None

        cache_data = {
            "project_type": self.project_config.project_type,
            "analyzed_at": datetime.now().isoformat(),
            "source_file": str(self.project_init_path),
            "repositories": repos_data,
        }

        analysis_filename = generate_analysis_filename(str(self.project_init_path))
        save_path = self.project_init_path.parent / analysis_filename

        save_path.write_text(json.dumps(cache_data, indent=2, default=str))
        print(f"   Saved codebase analysis cache: {save_path}")
        return str(save_path)

    def _load_codebase_analysis_cache(self) -> bool:
        """Load cached codebase analysis from disk.

        Looks for the analysis cache file alongside the input file.
        If found, populates self.codebase_analyses and patches
        self.project_config.repositories for multi-repo projects.

        Returns:
            True if cache was loaded successfully, False otherwise.
        """
        from ..utils.file_naming import extract_base_name

        base_name = extract_base_name(str(self.project_init_path))

        # The Feature phase receives the refined file (e.g., "reporting-change-refined.md").
        # extract_base_name produces "reporting-change-refined".
        # The Plan phase saved using the original base (e.g., "reporting-change").
        # Strip "-refined" suffix to find the cache file.
        stripped_base = re.sub(r"-refined$", "", base_name)

        candidates = []
        if stripped_base != base_name:
            candidates.append(
                self.project_init_path.parent / f"{stripped_base}-codebase-analysis.json"
            )
        candidates.append(
            self.project_init_path.parent / f"{base_name}-codebase-analysis.json"
        )

        cache_path = None
        for candidate in candidates:
            if candidate.exists():
                cache_path = candidate
                break

        if cache_path is None:
            return False

        try:
            content = cache_path.read_text()
            cache_data = json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            print(f"   Warning: Failed to load analysis cache from {cache_path}: {e}")
            return False

        repos = cache_data.get("repositories", {})
        if not repos:
            return False

        # Populate codebase_analyses dict
        for repo_id, entry in repos.items():
            analysis_data = entry.get("analysis", {})
            try:
                self.codebase_analyses[repo_id] = CodebaseAnalysis.model_validate(
                    analysis_data
                )
            except Exception as e:
                print(f"   Warning: Failed to parse analysis for {repo_id}: {e}")
                continue

        # Patch project_config.project_type from cache if parser misidentified it
        cached_project_type = cache_data.get("project_type")
        if cached_project_type in ("single_repo", "multi_repo"):
            self.project_config.project_type = cached_project_type

        # Patch project_config.repositories from cache if parser left it empty
        if cached_project_type == "multi_repo" and not self.project_config.repositories:
            self.project_config.repositories = [
                RepositoryConfig(
                    name=repo_id,
                    path=entry.get("path", ""),
                    language=entry.get("language", "unknown"),
                    framework=entry.get("framework"),
                    build_command=entry.get("build_command"),
                    test_command=entry.get("test_command"),
                )
                for repo_id, entry in repos.items()
            ]

        # Patch existing_codebase for single_repo
        if cached_project_type == "single_repo":
            if not self.project_config.existing_codebase:
                self.project_config.existing_codebase = {}
            for entry in repos.values():
                if entry.get("path"):
                    self.project_config.existing_codebase["path"] = entry["path"]
                    break

        analyzed_at = cache_data.get("analyzed_at", "unknown")
        print(f"   Loaded cached codebase analysis from: {cache_path}")
        print(f"   (analyzed at: {analyzed_at}, {len(self.codebase_analyses)} repo(s))")
        for repo_id, analysis in self.codebase_analyses.items():
            method = analysis.analysis_method or "unknown"
            print(f"      - {repo_id} (method: {method})")

        return True

    def _might_have_cached_analysis(self) -> bool:
        """Check if an analysis cache file might exist on disk.

        Used to guard against the case where the parser misidentifies a
        multi-repo refined file as 'new' because it can't parse the
        repository headers. This performs a cheap filesystem check.
        """
        from ..utils.file_naming import extract_base_name

        base_name = extract_base_name(str(self.project_init_path))
        stripped_base = re.sub(r"-refined$", "", base_name)

        candidates = [
            self.project_init_path.parent / f"{base_name}-codebase-analysis.json",
            self.project_init_path.parent / f"{stripped_base}-codebase-analysis.json",
        ]
        return any(c.exists() for c in candidates)

    async def generate_project_init_final(self) -> str:
        """Generate project-init-final.md with comprehensive project info using Claude.

        This method uses Claude to intelligently analyze the developer's input
        and enhance it with all aspects of software development that may be missing.

        Returns:
            Path to the generated file
        """
        if not self.project_config:
            raise ValueError("Must call parse_project() first")

        # Generate testing strategy
        testing_strategy = self._generate_testing_strategy()

        # Use Claude to enhance the specification
        print("\n🤖 Using Claude to enhance project specification...")
        print("   (Analyzing requirements, adding missing details, edge cases, etc.)")

        enhancer = SpecEnhancer(
            project_config=self.project_config,
            codebase_analyses=self.codebase_analyses if self.codebase_analyses else None,
            testing_strategy=testing_strategy,
            cost_tracker=self._cost_tracker,
        )

        # Get enhanced content from Claude
        enhanced_content = await enhancer.enhance()

        # Save the file with custom naming
        from ..utils.file_naming import generate_refined_filename
        refined_filename = generate_refined_filename(str(self.project_init_path))
        final_path = self.project_init_path.parent / refined_filename
        final_path.write_text(enhanced_content)

        print(f"\n📄 Generated enhanced specification at: {final_path}")
        return str(final_path)

    def save_feature_list(
        self, feature_list: FeatureList, output_path: Optional[str] = None
    ) -> str:
        """Save feature list to JSON file.

        Args:
            feature_list: The feature list to save
            output_path: Override output path

        Returns:
            Path to saved file
        """
        if output_path:
            save_path = Path(output_path)
        else:
            # Save next to project-init.md with custom naming
            from ..utils.file_naming import generate_features_filename
            features_filename = generate_features_filename(str(self.project_init_path))
            save_path = self.project_init_path.parent / features_filename

        # Convert to JSON
        data = feature_list.model_dump(mode="json")

        # Write file
        save_path.write_text(json.dumps(data, indent=2, default=str))

        print(f"\nFeature list saved to: {save_path}")
        return str(save_path)

    async def run_plan_phase(
        self,
        skip_requirements_validation: bool = False,
    ) -> str:
        """Run phase 1: Parse project and generate project-init-final.md.

        This is the first step of the three-step workflow:
        1. plan (this method) -> generates project-init-final.md
        2. feature -> generates feature_list.json
        3. develop -> implements features

        Args:
            skip_requirements_validation: If True, skip validation (use legacy format)

        Returns:
            Path to generated project-init-final.md
        """
        print(f"Reading project description from: {self.project_init_path}")

        # Step 1: Parse project
        self.parse_project()
        print(f"Project type: {self.project_config.project_type}")  # type: ignore

        # Step 1.5: Validate requirements sections
        if not skip_requirements_validation:
            missing = self.validate_requirements()
            if missing:
                print(f"\nValidating requirements sections...")
                if not self.prompt_for_missing_requirements(interactive=True):
                    raise MissingRequirementsError(missing, str(self.project_init_path))

        # Step 2: Analyze codebases (if existing repo)
        if self.project_config.project_type != "new":  # type: ignore
            print("\nAnalyzing existing codebase(s)...")
            await self.analyze_codebases()
            # Persist analysis for Feature phase reuse
            self._save_codebase_analysis_cache()

        # Step 3: Generate project-init-final.md using Claude for intelligent enhancement
        print("\nGenerating project-init-final.md...")
        final_path = await self.generate_project_init_final()

        return final_path

    async def run_feature_phase(
        self,
        output_path: Optional[str] = None,
    ) -> tuple[FeatureList, str]:
        """Run phase 2: Generate feature_list.json from project-init-final.md.

        This is the second step of the three-step workflow:
        1. plan -> generates project-init-final.md
        2. feature (this method) -> generates feature_list.json
        3. develop -> implements features

        Args:
            output_path: Override path for feature_list.json

        Returns:
            Tuple of (FeatureList, path to saved file)
        """
        print(f"Reading project configuration from: {self.project_init_path}")

        # Parse the project-init-final.md (or project-init.md)
        self.parse_project()
        print(f"Project type: {self.project_config.project_type}")  # type: ignore

        # Load cached analysis or run fresh analysis
        if self.project_config.project_type != "new" or self._might_have_cached_analysis():  # type: ignore
            if not self.codebase_analyses:
                loaded = self._load_codebase_analysis_cache()
                if not loaded:
                    print("\n   No cached analysis found, running fresh analysis...")
                    await self.analyze_codebases()

        # Generate features using Claude
        print("\nGenerating feature list using Claude...")
        feature_list = await self.generate_features()

        # Save feature list
        saved_path = self.save_feature_list(feature_list, output_path)

        return feature_list, saved_path

    async def run(
        self,
        output_path: Optional[str] = None,
        interactive: bool = True,
        skip_requirements_validation: bool = False,
    ) -> tuple[FeatureList, str]:
        """Run the complete planning pipeline (legacy - combines both phases).

        DEPRECATED: Use run_plan_phase() and run_feature_phase() separately.

        Args:
            output_path: Override path for feature_list.json
            interactive: If True, prompt user for missing requirements
            skip_requirements_validation: If True, skip validation (use legacy format)

        Returns:
            Tuple of (FeatureList, path to saved file)
        """
        print(f"Reading project description from: {self.project_init_path}")

        # Step 1: Parse project
        self.parse_project()
        print(f"Project type: {self.project_config.project_type}")  # type: ignore

        # Step 1.5: Validate requirements sections
        if not skip_requirements_validation:
            missing = self.validate_requirements()
            if missing:
                print(f"\nValidating requirements sections...")
                if not self.prompt_for_missing_requirements(interactive=interactive):
                    raise MissingRequirementsError(missing, str(self.project_init_path))

        # Step 2: Analyze codebases
        if self.project_config.project_type != "new":  # type: ignore
            print("\nAnalyzing existing codebase(s)...")
            await self.analyze_codebases()
            # Persist analysis for Feature phase reuse
            self._save_codebase_analysis_cache()

        # Step 3: Generate project-init-final.md for developer review using Claude
        print("\nGenerating project-init-final.md for review...")
        final_path = await self.generate_project_init_final()

        if interactive:
            print(f"\n{'='*60}")
            print("⚠️  DEVELOPER APPROVAL REQUIRED")
            print(f"{'='*60}")
            print(f"\nA summary file has been generated for your review:")
            print(f"  → {final_path}")
            print("\nThis file includes:")
            print("  - All your project requirements")
            print("  - Auto-generated testing strategy")
            if self.codebase_analyses:
                print("  - Detected codebase patterns")
            print()
            print("IMPORTANT: Review project-init-final.md carefully before proceeding.")
            print("The feature list will be generated based on this information.")
            print()
            print("Options:")
            print("  'approve' - Approve and proceed with feature generation")
            print("  'q'       - Quit and review/update project-init.md")
            print()

            while True:
                response = input("Enter your choice: ").strip().lower()

                if response == 'approve':
                    print("\n✓ Approved. Proceeding with feature generation...")
                    break
                elif response == 'q' or response == 'quit':
                    print("\nPlanning stopped. Please review project-init-final.md.")
                    print("If changes are needed, update project-init.md and run the plan command again.")
                    raise SystemExit(0)
                else:
                    print(f"Invalid choice '{response}'. Please type 'approve' or 'q'.")

        # Step 4: Generate features
        print("\nGenerating feature list...")
        feature_list = await self.generate_features()

        # Step 5: Save
        saved_path = self.save_feature_list(feature_list, output_path)

        # Print summary
        print(f"\n{'='*60}")
        print("Planning Complete")
        print(f"{'='*60}")
        print(f"Project: {feature_list.project_name}")
        print(f"Features: {len(feature_list.features)}")

        if feature_list.branch_name:
            print(f"Branch: {feature_list.branch_name}")

        print("\nFeatures to implement:")
        for i, feat in enumerate(feature_list.features, 1):
            deps = f" (depends on: {', '.join(feat.depends_on)})" if feat.depends_on else ""
            print(f"  {i}. {feat.id}: {feat.name}{deps}")

        print(f"\n→ Review {saved_path} and run 'develop' when ready")

        return feature_list, saved_path


def load_feature_list(path: str) -> FeatureList:
    """Load a feature list from JSON file.

    Args:
        path: Path to feature_list.json

    Returns:
        Loaded FeatureList
    """
    content = Path(path).read_text()
    data = json.loads(content)
    return FeatureList.model_validate(data)
