"""Generate feature list from project description using Claude via Bedrock."""

import json
import re
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import anthropic

from ..config import bedrock_config

if TYPE_CHECKING:
    from ..services.cost_tracker import CostTracker

from ..models.project import ProjectConfig
from ..models.feature import (
    FeatureList,
    Feature,
    RepoTask,
    Repository,
    CodebaseAnalysis,
    TechStack,
    RepoDependency,
)


class FeatureGenerator:
    """Generates structured feature list from project configuration."""

    def __init__(
        self,
        project_config: ProjectConfig,
        cost_tracker: Optional["CostTracker"] = None,
    ):
        """Initialize generator with project configuration.

        Args:
            project_config: Parsed project configuration
            cost_tracker: Optional CostTracker for recording API costs
        """
        self.project_config = project_config
        self._cost_tracker = cost_tracker

    async def generate(
        self,
        codebase_analyses: Optional[dict[str, CodebaseAnalysis]] = None,
        output_dir: Optional[str] = None,
        testing_strategy: Optional[dict] = None,
    ) -> FeatureList:
        """Generate feature list using Claude."""
        prompt = self._build_prompt(codebase_analyses)

        # Use Claude to generate features
        response = await self._query_claude(prompt)

        # Parse response into FeatureList
        feature_list = self._parse_response(
            response, codebase_analyses, output_dir, testing_strategy
        )

        return feature_list

    def _build_prompt(
        self, codebase_analyses: Optional[dict[str, CodebaseAnalysis]] = None
    ) -> str:
        """Build the prompt for Claude to generate features."""
        prompt = f"""You are an expert software architect. Analyze the following project description and generate a structured feature list.

## Project Description

{self.project_config.raw_content}

## Project Type

{self.project_config.project_type}

"""

        if codebase_analyses:
            prompt += """## Existing Codebase Analysis

"""
            for repo_id, analysis in codebase_analyses.items():
                prompt += f"""### Repository: {repo_id}

Structure:
{json.dumps(analysis.structure, indent=2)}

Patterns:
{json.dumps(analysis.patterns, indent=2)}

Testing:
{json.dumps(analysis.testing.model_dump() if analysis.testing else None, indent=2)}

"""
                # New fields from AI-agent analysis
                if analysis.architecture_patterns:
                    prompt += f"Architecture Patterns:\n{json.dumps(analysis.architecture_patterns, indent=2)}\n\n"
                if analysis.coding_conventions:
                    prompt += f"Coding Conventions:\n{json.dumps(analysis.coding_conventions, indent=2)}\n\n"
                if analysis.key_abstractions:
                    prompt += f"Key Abstractions:\n{json.dumps(analysis.key_abstractions, indent=2)}\n\n"
                if analysis.module_relationships:
                    prompt += f"Module Relationships:\n{json.dumps(analysis.module_relationships, indent=2)}\n\n"
                if analysis.api_patterns:
                    prompt += f"API Patterns:\n{json.dumps(analysis.api_patterns, indent=2)}\n\n"

        prompt += """## Instructions

Generate a JSON feature list with the following structure:

```json
{
  "project_name": "project-name-slug",
  "description": "Brief project description",
  "features": [
    {
      "id": "FEAT-001",
      "name": "Feature Name",
      "description": "What this feature does",
      "priority": 1,
      "depends_on": [],
      "repo_tasks": [
        {
          "repo_id": "main",
          "description": "What to do in this repo",
          "files": ["expected/file/paths.py"],
          "test_command": "pytest tests/"
        }
      ],
      "requires_tests": true,
      "acceptance_criteria": ["Criterion 1", "Criterion 2"],
      "test_criteria": ["Test case 1", "Test case 2"]
    }
  ]
}
```

## Requirements for Features:

1. **Break down into small, implementable features** - Each feature should be completable in one development session
2. **Order by dependency** - Features that others depend on should come first
3. **Include setup features** - Project setup, configuration, and infrastructure should be early features
4. **Each feature needs tests** - Define clear test criteria
5. **Respect existing patterns** - If working on existing repo, follow its conventions
6. **For multi-repo projects** - Use repo_tasks to specify work per repository

## Feature Guidelines:

- FEAT-001 should be project setup/scaffolding
- Break down into as many features as needed to fully implement the project
- Each feature should be completable in one development session
- Include comprehensive acceptance criteria (as many as needed)
- Include comprehensive test criteria (as many as needed)
- Include both unit and integration test criteria where appropriate
- Be thorough in descriptions - include all relevant details

## IMPORTANT: Output Format
- Generate ONLY valid JSON, no markdown code blocks or additional text
- Be comprehensive - include ALL features needed for a production-ready implementation
- Do not skip any important functionality
"""

        return prompt

    async def _query_claude(self, prompt: str) -> str:
        """Query Claude via Bedrock to generate features using streaming."""
        client = anthropic.AnthropicBedrock(
            aws_region=bedrock_config.region,
        )

        try:
            # Use streaming for large token limits (required by SDK for >10 min operations)
            full_response = ""
            stop_reason = None

            print("   Streaming response from Claude...", end="", flush=True)

            with client.messages.stream(
                model=bedrock_config.model_id,
                max_tokens=64000,  # Bedrock model limit
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    # Print progress indicator
                    if len(full_response) % 5000 == 0:
                        print(".", end="", flush=True)

                # Get the final message for stop_reason
                final_message = stream.get_final_message()
                stop_reason = final_message.stop_reason

            print(" Done!")

            # Capture token usage from streaming response
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens
            print(f"   📊 Tokens: {input_tokens:,} in / {output_tokens:,} out")

            if self._cost_tracker:
                entry = self._cost_tracker.record(
                    model_id=bedrock_config.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    phase="feature",
                    label="feature_generation",
                )
                print(f"   💰 Cost: {self._cost_tracker.format_cost(entry.total_cost)}")

        except Exception as e:
            raise RuntimeError(f"Failed to call Claude API: {e}")

        # Check if response was truncated
        if stop_reason == "max_tokens":
            print("⚠️  Warning: Response was truncated due to max_tokens limit.")

        if not full_response.strip():
            raise RuntimeError(
                f"Claude returned empty response. Stop reason: {stop_reason}. "
                f"This may be due to content filtering or model limitations."
            )

        return full_response

    def _parse_response(
        self,
        response: str,
        codebase_analyses: Optional[dict[str, CodebaseAnalysis]] = None,
        output_dir: Optional[str] = None,
        testing_strategy: Optional[dict] = None,
    ) -> FeatureList:
        """Parse Claude's response into a FeatureList."""
        # Extract JSON from response
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON (look for opening brace)
            brace_match = re.search(r"\{.*\}", response, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0)
            else:
                json_str = response.strip()

        if not json_str.strip():
            raise ValueError(
                f"Could not extract JSON from Claude's response. "
                f"Response preview: {response[:500] if response else '(empty)'}..."
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to repair truncated JSON
            repaired_json = self._repair_truncated_json(json_str)
            if repaired_json:
                try:
                    data = json.loads(repaired_json)
                    print("⚠️  Warning: JSON was truncated and auto-repaired. Some features may be missing.")
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Failed to parse Claude's response as JSON: {e}\n"
                        f"JSON string preview: {json_str[:500]}..."
                    )
            else:
                raise ValueError(
                    f"Failed to parse Claude's response as JSON: {e}\n"
                    f"JSON string preview: {json_str[:500]}..."
                )

        # Build features list
        features = []
        for feat_data in data.get("features", []):
            repo_tasks = []
            for task_data in feat_data.get("repo_tasks", []):
                repo_tasks.append(
                    RepoTask(
                        repo_id=task_data.get("repo_id", "main"),
                        description=task_data.get("description", ""),
                        files=task_data.get("files", []),
                        test_command=task_data.get("test_command"),
                    )
                )

            features.append(
                Feature(
                    id=feat_data.get("id", f"FEAT-{len(features)+1:03d}"),
                    name=feat_data.get("name", ""),
                    description=feat_data.get("description", ""),
                    priority=feat_data.get("priority", len(features) + 1),
                    depends_on=feat_data.get("depends_on", []),
                    repo_tasks=repo_tasks,
                    requires_tests=feat_data.get("requires_tests", True),
                    acceptance_criteria=feat_data.get("acceptance_criteria", []),
                    test_criteria=feat_data.get("test_criteria", []),
                )
            )

        # Build repositories list if multi-repo
        repositories = []
        if self.project_config.project_type == "multi_repo":
            for repo_config in self.project_config.repositories:
                analysis = (
                    codebase_analyses.get(repo_config.name)
                    if codebase_analyses
                    else None
                )
                repositories.append(
                    Repository(
                        id=repo_config.name,
                        path=repo_config.path,
                        language=repo_config.language,
                        framework=repo_config.framework,
                        codebase_analysis=analysis,
                    )
                )
        elif (
            self.project_config.project_type == "single_repo"
            and self.project_config.existing_codebase
        ):
            analysis = (
                codebase_analyses.get("main") if codebase_analyses else None
            )
            repositories.append(
                Repository(
                    id="main",
                    path=self.project_config.existing_codebase.get("path", ""),
                    language=self._detect_language_from_config(),
                    codebase_analysis=analysis,
                )
            )

        # Build repo dependencies
        repo_dependencies = []
        if self.project_config.cross_repo_dependencies:
            # Parse dependencies from text (e.g., "Database → Middleware → Frontend")
            deps_text = self.project_config.cross_repo_dependencies
            parts = re.split(r"[→>-]+", deps_text)
            parts = [p.strip().lower() for p in parts if p.strip()]
            for i in range(len(parts) - 1):
                repo_dependencies.append(
                    RepoDependency(upstream=parts[i], downstream=parts[i + 1])
                )

        # Build branch name for existing repos (always create feature branches)
        branch_name = None
        if self.project_config.project_type in ("single_repo", "multi_repo"):
            if self.project_config.jira_ticket:
                # With Jira ticket
                slug = self._generate_slug(data.get("project_name", self.project_config.title))
                branch_name = f"feature/{self.project_config.jira_ticket}-{slug}"
            else:
                # Without Jira ticket - generate default branch name
                slug = self._generate_slug(data.get("project_name", self.project_config.title))
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                branch_name = f"feature/agent-{slug}-{timestamp}"

        # Build tech stack for new projects
        tech_stack = None
        if self.project_config.project_type == "new" and self.project_config.tech_stack:
            tech_stack = TechStack(
                language=self.project_config.tech_stack.get("language", "python"),
                framework=self.project_config.tech_stack.get("framework"),
                database=self.project_config.tech_stack.get("database"),
            )

        return FeatureList(
            project_name=data.get("project_name", self._generate_slug(self.project_config.title)),
            description=data.get("description", self.project_config.introduction),
            project_type=self.project_config.project_type,
            jira_ticket=self.project_config.jira_ticket,
            branch_name=branch_name,
            tech_stack=tech_stack,
            output_directory=output_dir,
            repositories=repositories,
            repo_dependencies=repo_dependencies,
            features=features,
            testing_strategy=testing_strategy,
            generated_at=datetime.now(),
        )

    def _repair_truncated_json(self, json_str: str) -> Optional[str]:
        """Attempt to repair truncated JSON by closing open structures.

        Args:
            json_str: Potentially truncated JSON string

        Returns:
            Repaired JSON string or None if repair failed
        """
        # Count open brackets/braces
        open_braces = json_str.count('{') - json_str.count('}')
        open_brackets = json_str.count('[') - json_str.count(']')

        if open_braces <= 0 and open_brackets <= 0:
            return None  # Not a truncation issue

        repaired = json_str.rstrip()

        # Try to find the last complete feature by looking for patterns
        # Look for the last complete "}" that ends a feature object
        # Features are in an array, so we want to find "}, {" or "}]"

        # First, try to find the last complete feature
        last_feature_end = repaired.rfind('},')
        if last_feature_end > 0:
            # Check if this is within the features array
            features_start = repaired.find('"features"')
            if features_start > 0 and last_feature_end > features_start:
                # Cut at the last complete feature and close properly
                repaired = repaired[:last_feature_end + 1]
                # Recount after cutting
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')

        # Remove any trailing incomplete content
        # Strip trailing whitespace and partial tokens
        while repaired and repaired[-1] not in ['}', ']', '"', 'e', 'l', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
            repaired = repaired[:-1]

        # If we're in the middle of a string, try to close it
        quote_count = repaired.count('"') - repaired.count('\\"')
        if quote_count % 2 == 1:
            # Find and remove the incomplete string
            last_quote = repaired.rfind('"')
            if last_quote > 0:
                # Check if this is a key or value
                before_quote = repaired[:last_quote].rstrip()
                if before_quote.endswith(':'):
                    # Incomplete value, add empty string
                    repaired += '""'
                elif before_quote.endswith(',') or before_quote.endswith('['):
                    # Incomplete array element or object key
                    repaired = repaired[:last_quote]
                else:
                    # Just close the string
                    repaired += '"'

        # Recount after modifications
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')

        # Close any open arrays and objects in the right order
        # We need to close arrays before objects (inner before outer)
        # The structure is: { "features": [ {...}, {...} ] }

        # Close features array first, then root object
        repaired += ']' * open_brackets
        repaired += '}' * open_braces

        return repaired

    def _detect_language_from_config(self) -> str:
        """Detect primary language from project config."""
        if self.project_config.tech_stack:
            return self.project_config.tech_stack.get("language", "python")

        if self.project_config.existing_codebase:
            # Try to detect from test patterns or other hints
            path = self.project_config.existing_codebase.get("path", "")
            if "python" in path.lower() or ".py" in str(self.project_config.existing_codebase):
                return "python"
            elif "java" in path.lower():
                return "java"
            elif "typescript" in path.lower() or ".ts" in str(self.project_config.existing_codebase):
                return "typescript"

        return "python"

    def _generate_slug(self, text: str) -> str:
        """Generate a URL-friendly slug from text."""
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Limit length
        return slug[:50]
