"""Prompt templates for the autonomous coding agent."""

from typing import Optional
from ..models.feature import Feature, FeatureList, CodebaseAnalysis
from ..models.state import AgentState


class PromptTemplates:
    """Templates for various agent prompts."""

    @staticmethod
    def get_system_prompt(feature_list: FeatureList) -> str:
        """Generate the system prompt for development sessions."""
        return f"""You are an autonomous coding agent working on the project: {feature_list.project_name}

## Project Overview
{feature_list.description}

## Project Type
{feature_list.project_type}

## Available Tools
You have access to the following tools to implement features:

1. **write_file** - Create or overwrite files with content
2. **read_file** - Read the contents of existing files
3. **list_directory** - List files and directories
4. **execute_command** - Run shell commands (for tests, installing dependencies, etc.)
5. **create_directory** - Create directories

USE THESE TOOLS to actually implement the code. Do not just describe what to do - use the tools to write actual files.

## Your Responsibilities
1. Use tools to implement features according to the specifications
2. Write comprehensive tests for all code
3. Run tests using execute_command and ensure they pass
4. Follow existing code patterns and conventions
5. Create well-structured, maintainable code

## Important Guidelines
- ALWAYS use write_file to create actual code files
- ALWAYS write tests for your code
- Use execute_command to run tests after implementation
- If tests fail, fix the code and run tests again
- Follow existing codebase patterns if working on an existing repo
- Keep implementations simple and focused
- Document complex logic with comments

## Testing Requirements
- Every feature with code changes MUST have tests
- Tests must pass before the feature is considered complete
- If tests fail, analyze the failure and fix the code
- Iterate until all tests pass
"""
        # Add testing strategy if available
        if feature_list.testing_strategy:
            strategy = feature_list.testing_strategy
            prompt += "\n## Testing Strategy\n"

            if strategy.get("strategy") == "multi_repo":
                prompt += "*Testing per repository:*\n"
                for repo_id, repo_strat in strategy.get("repositories", {}).items():
                    prompt += f"\n### {repo_id}\n"
                    prompt += f"- **Framework**: {repo_strat.get('framework', 'unknown')}\n"
                    prompt += f"- **Command**: `{repo_strat.get('command', 'N/A')}`\n"
                    commit_tests = repo_strat.get('commit_tests', True)
                    prompt += f"- **Commit Tests**: {'Yes' if commit_tests else 'NO - Run locally only, do NOT commit test files'}\n"
                    if not commit_tests:
                        prompt += f"  ⚠️ {repo_strat.get('warning', 'Tests validated locally only')}\n"
            else:
                prompt += f"- **Framework**: {strategy.get('framework', 'unknown')}\n"
                prompt += f"- **Test Command**: `{strategy.get('command', 'pytest')}`\n"
                if strategy.get("coverage_command"):
                    prompt += f"- **Coverage Command**: `{strategy['coverage_command']}`\n"
                commit_tests = strategy.get('commit_tests', True)
                prompt += f"- **Commit Tests**: {'Yes' if commit_tests else 'NO - Run locally only, do NOT commit test files'}\n"
                if not commit_tests:
                    prompt += f"\n⚠️ IMPORTANT: {strategy.get('warning', 'Tests should be validated locally but NOT committed to the repository.')}\n"

        return prompt

    @staticmethod
    def get_feature_implementation_prompt(
        feature: Feature,
        feature_list: FeatureList,
        completed_features: list[str],
        codebase_analysis: Optional[CodebaseAnalysis] = None,
        previous_summary: Optional[str] = None,
    ) -> str:
        """Generate prompt to implement a specific feature."""
        prompt = f"""# Feature Implementation Task

## Feature Details
- **ID**: {feature.id}
- **Name**: {feature.name}
- **Description**: {feature.description}

## Acceptance Criteria
"""
        for criterion in feature.acceptance_criteria:
            prompt += f"- {criterion}\n"

        prompt += "\n## Test Criteria\n"
        for test in feature.test_criteria:
            prompt += f"- {test}\n"

        if feature.repo_tasks:
            prompt += "\n## Repository Tasks\n"
            for task in feature.repo_tasks:
                prompt += f"""
### Repository: {task.repo_id}
- **Description**: {task.description}
- **Expected Files**: {', '.join(task.files) if task.files else 'TBD'}
- **Test Command**: {task.test_command or 'pytest'}
"""

        if completed_features:
            prompt += f"\n## Previously Completed Features\n"
            prompt += "The following features have been completed:\n"
            for feat_id in completed_features:
                prompt += f"- {feat_id}\n"

        if codebase_analysis:
            prompt += "\n## Codebase Patterns\n"
            prompt += "Follow these existing patterns:\n"

            if codebase_analysis.patterns:
                for key, value in codebase_analysis.patterns.items():
                    prompt += f"- **{key}**: {value}\n"

            if codebase_analysis.architecture_patterns:
                prompt += "\n**Architecture:**\n"
                for pattern in codebase_analysis.architecture_patterns:
                    prompt += f"- {pattern}\n"

            if codebase_analysis.coding_conventions:
                prompt += "\n**Coding Conventions (follow these):**\n"
                for name, desc in codebase_analysis.coding_conventions.items():
                    prompt += f"- **{name}**: {desc}\n"

            if codebase_analysis.key_abstractions:
                prompt += "\n**Key Abstractions (build on these):**\n"
                for a in codebase_analysis.key_abstractions:
                    prompt += f"- `{a.get('name', '?')}` ({a.get('type', '')}): {a.get('purpose', '')}\n"

            if codebase_analysis.testing:
                prompt += f"\n**Testing**: Use {codebase_analysis.testing.framework}\n"
                prompt += f"**Test Command**: `{codebase_analysis.testing.command}`\n"

        if previous_summary:
            prompt += f"\n## Context from Previous Session\n{previous_summary}\n"

        # Add testing strategy from feature list
        if feature_list.testing_strategy:
            strategy = feature_list.testing_strategy
            prompt += "\n## Testing Strategy\n"

            if strategy.get("strategy") == "multi_repo":
                # Find relevant repo strategy for this feature's tasks
                for task in feature.repo_tasks:
                    repo_strat = strategy.get("repositories", {}).get(task.repo_id)
                    if repo_strat:
                        prompt += f"**{task.repo_id}**: Use `{repo_strat.get('command', 'N/A')}`\n"
                        if not repo_strat.get('commit_tests', True):
                            prompt += f"⚠️ DO NOT commit test files - validate locally only\n"
            else:
                prompt += f"- **Test Command**: `{strategy.get('command', 'pytest')}`\n"
                if not strategy.get('commit_tests', True):
                    prompt += f"\n⚠️ **IMPORTANT**: DO NOT commit test files to the repository.\n"
                    prompt += "Run tests locally to validate, but do not include test files in commits.\n"

        prompt += """
## Instructions

IMPORTANT: Use the available tools to actually write code files. Do not just describe what to do.

1. **Use write_file tool** to create the implementation files
2. **Use write_file tool** to create test files
3. **Use execute_command tool** to run tests
4. If tests fail, **fix the code** using write_file and run tests again
5. Continue until all tests pass

Start implementing now. First analyze what needs to be done, then USE THE TOOLS to create actual files.
"""

        return prompt

    @staticmethod
    def get_handoff_summary_prompt() -> str:
        """Generate prompt to create a handoff summary."""
        return """Please provide a concise summary of what has been accomplished in this session.

Include:
1. **Features Completed**: List features that were successfully implemented
2. **Current Progress**: What you were working on when the session ended
3. **Files Modified**: Key files that were created or changed
4. **Decisions Made**: Important technical decisions or patterns established
5. **Next Steps**: What should be done next

This summary will be used to continue work in a new session. Be specific but concise.
"""

    @staticmethod
    def get_test_fix_prompt(
        feature: Feature,
        test_output: str,
        attempt_number: int,
    ) -> str:
        """Generate prompt to fix failing tests."""
        return f"""# Test Failure - Fix Required

## Feature: {feature.name} ({feature.id})

## Test Output
```
{test_output}
```

## Attempt: {attempt_number}

The tests are failing. Please:

1. **Analyze the failure** - Understand what went wrong
2. **Identify the root cause** - Is it in the implementation or the test?
3. **Fix the code** - Make the necessary changes
4. **Run tests again** - Verify the fix works

Focus on fixing the actual issue, not just making tests pass superficially.
"""

    @staticmethod
    def get_validation_prompt(feature: Feature) -> str:
        """Generate prompt to validate feature implementation.

        Asks Claude to run tests, check acceptance/test criteria,
        and return a structured JSON report.
        """
        criteria_list = "\n".join(f"- {c}" for c in feature.acceptance_criteria)
        test_list = "\n".join(f"- {t}" for t in feature.test_criteria)

        return f"""# Feature Validation Required

## Feature: {feature.name} ({feature.id})

You have just finished implementing this feature. Now you MUST validate your work before it can be marked as complete.

## Steps to Validate

1. **Run all tests** related to this feature using `execute_command`
2. **Check each acceptance criterion** below — verify it is actually met by the code you wrote
3. **Check each test criterion** below — verify tests exist and pass

## Acceptance Criteria
{criteria_list}

## Test Criteria
{test_list}

## Required Response Format

After running tests and checking criteria, respond with EXACTLY this JSON block:

```json
{{{{
  "validated": true,
  "tests_passed": true,
  "test_output_summary": "brief summary of test results",
  "criteria_results": [
    {{{{"criterion": "...", "met": true, "evidence": "..."}}}}
  ],
  "issues": [],
  "fix_needed": ""
}}}}
```

IMPORTANT:
- You MUST actually run the tests using execute_command — do not just assume they pass
- Set "validated" to true ONLY if ALL tests pass AND ALL acceptance criteria are met
- If anything fails, set "validated" to false and describe what needs fixing in "fix_needed"
- The "issues" array should list each specific problem found
"""

    @staticmethod
    def get_validation_fix_prompt(
        feature: Feature,
        validation_result: dict,
        attempt_number: int,
    ) -> str:
        """Generate prompt to fix validation failures."""
        issues = "\n".join(
            f"- {i}" for i in validation_result.get("issues", [])
        )
        fix_needed = validation_result.get("fix_needed", "Unknown issue")
        test_summary = validation_result.get(
            "test_output_summary", "No test output available"
        )

        return f"""# Validation Failed - Fix Required (Attempt {attempt_number})

## Feature: {feature.name} ({feature.id})

## What Failed
{fix_needed}

## Issues Found
{issues}

## Test Output Summary
{test_summary}

## Instructions

1. Analyze the failures above
2. Fix the code and/or tests
3. Run tests again to verify the fix
4. After fixing, I will ask you to validate again

Focus on fixing the root cause, not just making tests pass superficially.
Start fixing now — use the tools to update files and run tests.
"""

    @staticmethod
    def get_context_continuation_prompt(
        state: AgentState,
        feature_list: FeatureList,
        current_feature: Optional[Feature] = None,
    ) -> str:
        """Generate prompt for continuing work from a previous session."""
        prompt = f"""# Project Continuation

## Session Info
- **Session Number**: {state.context_tracking.session_count + 1}
- **Previous Sessions**: {state.context_tracking.session_count}

## Project: {feature_list.project_name}
- **Type**: {feature_list.project_type}
"""

        if feature_list.branch_name:
            prompt += f"- **Branch**: {feature_list.branch_name}\n"

        # Completed features
        completed = state.get_completed_feature_ids()
        if completed:
            prompt += "\n## Completed Features\n"
            for feat_id in completed:
                # Find feature name
                for feat in feature_list.features:
                    if feat.id == feat_id:
                        status = state.features_status.get(feat_id)
                        commit = status.commit_hash if status else "N/A"
                        prompt += f"- {feat_id}: {feat.name} (commit: {commit})\n"
                        break

        # Current feature
        if current_feature:
            prompt += f"\n## Current Feature (In Progress)\n"
            prompt += f"- **ID**: {current_feature.id}\n"
            prompt += f"- **Name**: {current_feature.name}\n"
            prompt += f"- **Description**: {current_feature.description}\n"

        # Remaining features
        remaining = [
            f for f in feature_list.features
            if f.id not in completed and (not current_feature or f.id != current_feature.id)
        ]
        if remaining:
            prompt += "\n## Remaining Features\n"
            for feat in remaining:
                prompt += f"- {feat.id}: {feat.name}\n"

        # Previous summary
        if state.conversation_summary:
            prompt += f"\n## Previous Session Summary\n{state.conversation_summary}\n"

        prompt += """
## Instructions

Continue implementing features from where the previous session left off.
"""
        if current_feature:
            prompt += f"Start with completing {current_feature.id}: {current_feature.name}\n"
        else:
            prompt += "Start with the next pending feature.\n"

        return prompt

    @staticmethod
    def get_new_project_setup_prompt(feature_list: FeatureList) -> str:
        """Generate prompt for setting up a new project."""
        prompt = f"""# New Project Setup

## Project: {feature_list.project_name}
{feature_list.description}

"""

        if feature_list.tech_stack:
            prompt += "## Technology Stack\n"
            prompt += f"- **Language**: {feature_list.tech_stack.language}\n"
            if feature_list.tech_stack.framework:
                prompt += f"- **Framework**: {feature_list.tech_stack.framework}\n"
            if feature_list.tech_stack.database:
                prompt += f"- **Database**: {feature_list.tech_stack.database}\n"

        if feature_list.output_directory:
            prompt += f"\n## Output Directory\n{feature_list.output_directory}\n"

        prompt += """
## Setup Instructions

1. Create the project directory structure
2. Initialize any package managers (pip, npm, etc.)
3. Create configuration files
4. Set up the basic application structure
5. Create initial test configuration

Start by creating the project structure.
"""

        return prompt
