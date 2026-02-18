"""Enhance project specifications using Claude via Bedrock.

This service uses Claude to intelligently analyze a developer's project-init.md
and enhance it with comprehensive software development details that may be missing.
"""

import anthropic
from typing import Optional, TYPE_CHECKING

from ..config import bedrock_config

if TYPE_CHECKING:
    from ..services.cost_tracker import CostTracker

from ..models.project import ProjectConfig
from ..models.feature import CodebaseAnalysis


class SpecEnhancer:
    """Enhances project specifications using Claude for intelligent analysis."""

    def __init__(
        self,
        project_config: ProjectConfig,
        codebase_analyses: Optional[dict[str, CodebaseAnalysis]] = None,
        testing_strategy: Optional[dict] = None,
        cost_tracker: Optional["CostTracker"] = None,
    ):
        """Initialize the spec enhancer.

        Args:
            project_config: Parsed project configuration
            codebase_analyses: Analysis of existing codebases (if any)
            testing_strategy: Auto-generated testing strategy
            cost_tracker: Optional CostTracker for recording API costs
        """
        self.project_config = project_config
        self.codebase_analyses = codebase_analyses or {}
        self.testing_strategy = testing_strategy or {}
        self._cost_tracker = cost_tracker

    async def enhance(self) -> str:
        """Enhance the project specification using Claude.

        Returns:
            Enhanced project-init-final.md content as markdown string
        """
        prompt = self._build_enhancement_prompt()
        enhanced_content = await self._query_claude(prompt)
        return enhanced_content

    def _build_enhancement_prompt(self) -> str:
        """Build the comprehensive prompt for Claude to enhance the specification."""

        # Build context about what the developer provided
        developer_input = self._format_developer_input()
        codebase_context = self._format_codebase_context()

        prompt = f"""You are an expert software architect and technical lead. Your task is to enhance a developer's project specification to create a comprehensive, production-ready project-init-final.md document.

## IMPORTANT CONTEXT

The developer has provided a project-init.md file with their requirements. However, developers often:
- Forget critical implementation details
- Assume the agent will figure out edge cases
- Skip non-functional requirements
- Miss error handling scenarios
- Overlook security considerations
- Forget about logging, monitoring, and observability
- Skip API contract details
- Miss database schema considerations
- Overlook configuration management

Your job is to **intelligently fill in ALL missing aspects** while respecting what the developer explicitly specified.

## DEVELOPER'S ORIGINAL INPUT

{developer_input}

{codebase_context}

## WHAT YOU MUST ADD/ENHANCE

Analyze the developer's input and enhance it with the following aspects. Only add what's relevant to this specific project:

### 1. Functional Requirements Enhancement
- Break down high-level requirements into specific, testable requirements
- Add edge cases the developer may have missed
- Ensure each requirement has clear acceptance criteria
- Add user-facing error scenarios
- Consider different user roles/permissions if applicable

### 2. System Requirements (Non-Functional)
- **Performance**: Response time targets, throughput expectations
- **Security**: Authentication, authorization, data protection, input validation
- **Scalability**: Expected load, horizontal/vertical scaling considerations
- **Reliability**: Uptime requirements, fault tolerance, graceful degradation
- **Observability**: Logging strategy, metrics, health checks

### 3. API Contract Details (if applicable)
- Endpoint specifications with HTTP methods
- Request/response schemas
- Error response formats
- Status codes for different scenarios
- Authentication requirements per endpoint

### 4. Data Model & Storage (if applicable)
- Entity relationships
- Data validation rules
- Index requirements
- Data migration considerations

### 5. Error Handling Strategy
- Error categories and how each should be handled
- User-facing error messages
- Logging requirements for errors
- Retry strategies for external dependencies

### 6. Configuration Management
- Environment-specific configurations
- Secrets management approach
- Feature flags (if applicable)

### 7. Integration Points
- External services/APIs
- Database connections
- Message queues (if applicable)
- Third-party dependencies

### 8. Edge Cases & Boundary Conditions
- Input validation boundaries
- Empty/null handling
- Concurrent access scenarios
- Rate limiting considerations

## OUTPUT FORMAT

Generate a complete project-init-final.md document in the following markdown format. Be comprehensive but practical - only include sections relevant to this project:

```markdown
# [Project Title]

## Project Overview
[Enhanced description with clear scope]

## Project Type
[new/single_repo/multi_repo]

[Include Jira Ticket if provided]

## Technology Stack
[Tech stack details]

## Functional Requirements

### Core Features
- FR-1: [Specific, testable requirement]
  - Acceptance: [Clear acceptance criteria]
  - Edge Cases: [Edge cases to handle]
- FR-2: ...

### User Interactions
- FR-X: [User-facing behavior]
- ...

### Error Scenarios
- FR-ERR-1: [How system handles specific error]
- ...

## System Requirements

### Performance
- SR-PERF-1: [Specific performance requirement]
- ...

### Security
- SR-SEC-1: [Security requirement]
- ...

### Reliability
- SR-REL-1: [Reliability requirement]
- ...

### Observability
- SR-OBS-1: [Logging/monitoring requirement]
- ...

## API Specifications (if applicable)
[Endpoint details, schemas, error responses]

## Data Model (if applicable)
[Entity definitions, relationships, validation rules]

## Error Handling Strategy
[Error categories, handling approach, user messages]

## Configuration
[Environment configs, secrets approach]

## Integration Points
[External dependencies, how to handle failures]

## Success Criteria
[Measurable criteria for project success]

## Testing Strategy (Auto-Generated)
[Include the testing strategy]

## Codebase Analysis (if existing repo)
[Include codebase patterns]

---
*This file was generated by the Autonomous Coding Agent.*
*Please review all sections before proceeding with feature generation.*
*Once approved, run: `python main.py feature project-init-final.md` to generate the feature list.*
```

## CRITICAL INSTRUCTIONS

1. **Respect explicit specifications**: Don't change what the developer explicitly specified
2. **Trust codebase analysis over developer input on factual matters**: If the codebase analysis contradicts the developer's input regarding build tools, languages, test frameworks, directory structure, or file paths, trust the codebase analysis (it was generated from the actual repository). Flag any discrepancies you find in the output.
3. **Add implicit requirements**: Fill in details the developer likely assumed
4. **Be practical**: Only add requirements relevant to this specific project
5. **Be specific**: Each requirement should be implementable and testable
6. **Use consistent IDs**: FR-X for functional, SR-X for system requirements
7. **Prioritize completeness**: The feature generator will use this document, so nothing should be left to assumption
8. **Don't over-engineer**: Add only what's necessary for a production-ready implementation

Generate the complete enhanced project-init-final.md document now. Output ONLY the markdown content, no additional commentary."""

        return prompt

    def _format_developer_input(self) -> str:
        """Format the developer's original input for the prompt."""
        config = self.project_config

        content = f"""### Project Title
{config.title}

### Introduction
{config.introduction}

### Project Type
{config.project_type}
"""

        if config.jira_ticket:
            content += f"""
### Jira Ticket
{config.jira_ticket}
"""

        if config.tech_stack:
            content += """
### Technology Stack
"""
            for key, value in config.tech_stack.items():
                content += f"- {key}: {value}\n"

        if config.existing_codebase:
            content += """
### Existing Codebase
"""
            for key, value in config.existing_codebase.items():
                content += f"- {key}: {value}\n"

        if config.repositories:
            content += """
### Repositories
"""
            for repo in config.repositories:
                content += f"""
#### {repo.name}
- Path: {repo.path}
- Language: {repo.language}
"""
                if repo.framework:
                    content += f"- Framework: {repo.framework}\n"
                if repo.test_command:
                    content += f"- Test Command: {repo.test_command}\n"

        if config.functional_requirements:
            content += """
### Functional Requirements (Developer Provided)
"""
            for req in config.functional_requirements:
                content += f"- {req}\n"

        if config.system_requirements:
            content += """
### System Requirements (Developer Provided)
"""
            for req in config.system_requirements:
                content += f"- {req}\n"

        if config.success_criteria:
            content += """
### Success Criteria (Developer Provided)
"""
            for criterion in config.success_criteria:
                content += f"- {criterion}\n"

        # Include raw content for any additional context
        if config.raw_content:
            content += f"""
### Full Original Document
```markdown
{config.raw_content}
```
"""

        return content

    def _format_codebase_context(self) -> str:
        """Format codebase analysis for the prompt."""
        if not self.codebase_analyses:
            return ""

        content = """
## EXISTING CODEBASE ANALYSIS

The agent has analyzed the existing codebase(s). Follow these patterns:

"""
        for repo_id, analysis in self.codebase_analyses.items():
            content += f"""### {repo_id}

"""
            if analysis.structure:
                content += "**Directory Structure:**\n"
                for path, desc in analysis.structure.items():
                    content += f"- `{path}`: {desc}\n"
                content += "\n"

            if analysis.patterns:
                content += "**Code Patterns:**\n"
                for pattern, value in analysis.patterns.items():
                    content += f"- {pattern}: {value}\n"
                content += "\n"

            if analysis.testing:
                content += f"""**Testing:**
- Framework: {analysis.testing.framework}
- Command: `{analysis.testing.command}`
"""

            # --- New fields from AI-agent analysis ---
            if analysis.architecture_patterns:
                content += "**Architecture Patterns:**\n"
                for pattern in analysis.architecture_patterns:
                    content += f"- {pattern}\n"
                content += "\n"

            if analysis.coding_conventions:
                content += "**Coding Conventions:**\n"
                for conv_name, conv_desc in analysis.coding_conventions.items():
                    content += f"- **{conv_name}**: {conv_desc}\n"
                content += "\n"

            if analysis.key_abstractions:
                content += "**Key Abstractions:**\n"
                for abstraction in analysis.key_abstractions:
                    name = abstraction.get("name", "Unknown")
                    atype = abstraction.get("type", "")
                    purpose = abstraction.get("purpose", "")
                    content += f"- `{name}` ({atype}): {purpose}\n"
                content += "\n"

            if analysis.module_relationships:
                content += "**Module Relationships:**\n"
                for rel in analysis.module_relationships:
                    src = rel.get("from", "?")
                    dst = rel.get("to", "?")
                    rtype = rel.get("relationship", "depends on")
                    content += f"- `{src}` -> `{dst}` ({rtype})\n"
                content += "\n"

            if analysis.api_patterns:
                content += "**API Patterns:**\n"
                for key, value in analysis.api_patterns.items():
                    content += f"- **{key}**: {value}\n"
                content += "\n"

            if analysis.entry_points:
                content += "**Entry Points:**\n"
                for ep in analysis.entry_points:
                    content += f"- `{ep}`\n"
                content += "\n"

        # Include testing strategy
        if self.testing_strategy:
            content += """
## AUTO-GENERATED TESTING STRATEGY

Include this in the final document:

"""
            if self.testing_strategy.get("strategy") == "multi_repo":
                content += "*Testing strategy per repository:*\n\n"
                for repo_id, repo_strategy in self.testing_strategy.get("repositories", {}).items():
                    content += f"### {repo_id}\n"
                    content += f"- Framework: {repo_strategy.get('framework', 'unknown')}\n"
                    content += f"- Command: `{repo_strategy.get('command', 'N/A')}`\n"
                    content += f"- Commit Tests: {'Yes' if repo_strategy.get('commit_tests') else 'No (local validation only)'}\n"
                    if repo_strategy.get("warning"):
                        content += f"- Warning: {repo_strategy['warning']}\n"
                    content += "\n"
            else:
                content += f"- Strategy: {self.testing_strategy.get('strategy', 'unknown')}\n"
                content += f"- Framework: {self.testing_strategy.get('framework', 'unknown')}\n"
                content += f"- Test Command: `{self.testing_strategy.get('command', 'N/A')}`\n"
                if self.testing_strategy.get("coverage_command"):
                    content += f"- Coverage Command: `{self.testing_strategy['coverage_command']}`\n"
                content += f"- Details: {self.testing_strategy.get('details', '')}\n"
                content += f"- Commit Tests: {'Yes' if self.testing_strategy.get('commit_tests', True) else 'No (local validation only)'}\n"
                if self.testing_strategy.get("warning"):
                    content += f"\nWarning: {self.testing_strategy['warning']}\n"

        return content

    async def _query_claude(self, prompt: str) -> str:
        """Query Claude via Bedrock to enhance the specification using streaming.

        Args:
            prompt: The enhancement prompt

        Returns:
            Enhanced specification content
        """
        client = anthropic.AnthropicBedrock(
            aws_region=bedrock_config.region,
        )

        try:
            # Use streaming for large responses
            full_response = ""

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

                # Get final message for any warnings
                final_message = stream.get_final_message()
                if final_message.stop_reason == "max_tokens":
                    print("\n⚠️  Warning: Response was truncated.")

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
                    phase="plan",
                    label="spec_enhancement",
                )
                print(f"   💰 Cost: {self._cost_tracker.format_cost(entry.total_cost)}")

        except Exception as e:
            raise RuntimeError(f"Failed to call Claude API: {e}")

        return full_response.strip()
