# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An autonomous coding agent that reads project descriptions and implements features autonomously using Claude via AWS Bedrock. The agent follows a three-phase workflow (Plan → Feature → Develop) with explicit approval points and feature-based implementation sessions.

**Key Philosophy**: The agent develops code by default without any Git/GitHub complexity. Pull Request creation is purely opt-in and requires developer-managed repository setup.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure AWS credentials (required for Bedrock access)
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile  # Optional: if using named profile

# Test the CLI
python main.py --help
```

### Main CLI Commands
```bash
# Step 1: Planning Phase - Generate project-init-final.md
python main.py plan project-init.md
python main.py plan project-init.md --repo /path/to/repo
python main.py plan project-init.md --multi-repo
python main.py plan project-init.md --skip-requirements-validation

# Step 2: Feature Generation - Generate feature_list.json
python main.py feature project-init-final.md
python main.py feature project-init-final.md -o /output/dir
python main.py feature project-init-final.md --feature-list-output /custom/path.json

# Step 3: Development - Implement features
python main.py develop feature_list.json
python main.py develop feature_list.json --resume
python main.py develop feature_list.json --feature FEAT-002
python main.py develop feature_list.json --comprehensive-testing
python main.py develop feature_list.json --comprehensive-testing --create-smart-prs

# Status and reporting
python main.py status feature_list.json
python main.py confidence-report feature_list.json
```

### Testing
- No test suite for the agent itself
- Agent generates and runs tests for user projects
- Dependencies are minimal: `anthropic[bedrock]>=0.40.0`, `pydantic>=2.0.0`

## Requirements

- Python 3.10+
- AWS credentials configured with Bedrock access to Claude models
- For PR creation: GitHub CLI (`gh`) authenticated and repositories configured

## Architecture & Key Components

### Three-Phase Pipeline Architecture
```
Plan Phase (src/pipeline/planning.py)
├── Parse project-init.md
├── Analyze existing codebase (if applicable)
├── Use Claude to enhance specifications
└── Generate project-init-final.md

Feature Phase (src/pipeline/planning.py)
├── Break down requirements into features
├── Determine feature dependencies
└── Generate feature_list.json

Develop Phase (src/pipeline/development.py)
├── Feature-based Claude sessions
├── Comprehensive testing (optional)
└── Smart PR creation (optional)
```

### Core Directory Structure
- **`/src/models/`**: Pydantic data models for features, state, testing, pull requests
- **`/src/services/`**: Business logic services
  - `codebase_analyzer.py`: AI-agent-based codebase analysis with deterministic fallback
  - `git_manager.py`, `state_manager.py`: Core state and version control
  - `comprehensive_tester.py`: Test suite generation and execution
  - `smart_pr_manager.py`: Intelligent PR creation service (opt-in only)
- **`/src/agent/`**: Claude Code SDK integration and session management
  - `core.py`: Main agent session orchestration
  - `session.py`: Individual Claude sessions
  - `tools.py`: Agent tool definitions (includes read-only tools for analysis)
  - `prompts.py`: Prompt templates
- **`/src/pipeline/`**: Main execution pipelines for each phase
- **`/templates/`**: Reference templates for project initialization

### Key Design Patterns

**Feature-based sessions**: Each feature gets its own Claude agent session to avoid context pollution - this is critical for handling testing cycles that can consume 85-100% of context.

**State persistence**: Progress tracked in `.agent-state.json` for seamless resume capability using `src/services/state_manager.py`.

**Codebase analysis**: `src/services/codebase_analyzer.py` uses a two-phase approach: (1) deterministic file tree collection, then (2) a bounded Claude agent session (Sonnet 4, 12 turns) with read-only tools that explores the codebase to understand architecture, patterns, conventions, and key abstractions. Falls back to deterministic-only analysis if the agent fails. Configured via `AnalysisConfig` in `src/config.py`.

**Working directory resolution**: Agent automatically determines correct working directory:
- New projects: Uses `output_directory`
- Single repo: Uses `repositories[0].path`
- Multi-repo: Uses first repo path as base

## Configuration

### AWS Bedrock Models (`src/config.py`)
```python
# Default: Claude Opus 4.6 (most capable)
OPUS_4_6 = "us.anthropic.claude-opus-4-6-20250610-v1:0"
OPUS_4_5 = "us.anthropic.claude-opus-4-5-20251101-v1:0"
SONNET_4 = "us.anthropic.claude-sonnet-4-20250514-v1:0"

# Override via environment variable
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

### Agent Configuration
- `AGENT_MAX_TURNS=50`: Maximum turns per session
- `CONTEXT_THRESHOLD=0.75`: Context threshold for handoff
- `MAX_CONTEXT_TOKENS=200000`: Maximum context tokens

### Codebase Analysis Configuration
- `ANALYSIS_MODEL_ID`: Model for analysis sessions (default: Sonnet 4)
- `ANALYSIS_MAX_TURNS=12`: Max tool-use turns per repo analysis
- `ANALYSIS_USE_AGENT=true`: Set to `false` to force deterministic-only analysis
- `ANALYSIS_MAX_TREE_DEPTH=4`: File tree depth for agent's initial context

## File I/O Patterns

**Important**: The agent operates on USER project files, not files in this repository.

### Input Files (User creates)
- `project-init.md`: User's project description

### Generated Files (Agent creates in user's project directory)
- `project-init-final.md`: Enhanced specification (plan phase)
- `feature_list.json`: Feature breakdown (feature phase)
- `.agent-state.json`: Progress tracking (develop phase)
- `comprehensive_test_report.json`: Test results (if `--comprehensive-testing`)
- `smart_pr_plan.json`: PR organization (if `--create-smart-prs`)

### State Management
The `StateManager` (`src/services/state_manager.py`) handles:
- Feature completion tracking
- Session context handoffs
- Branch management
- PR creation state
- Resume capability after interruptions

## Development Modes & Features

The agent supports three distinct development modes:

### Mode 1: Local Development (Default)
- **Command**: `python main.py develop feature_list.json`
- **Perfect for**: Experimentation, learning, prototyping, studying generated code
- **What it does**:
  - **New Projects**: Implements features in specified output directory
  - **Existing Repos**: Adds features directly to your existing codebase, respects existing patterns
- **Output**: Clean code ready for study or further development

### Mode 2: Enhanced Testing
- **Command**: `python main.py develop feature_list.json --comprehensive-testing`
- **Adds**: Extensive test coverage beyond individual feature tests
  - Integration tests (how features work together)
  - End-to-end workflow tests (real user scenarios)
  - Stress/performance tests (load handling)
  - Failure scenario tests (error handling)
- **Output**: Fully tested codebase with confidence metrics

### Mode 3: Production Ready
- **Command**: `python main.py develop feature_list.json --comprehensive-testing --create-smart-prs`
- **Prerequisites**: GitHub repository/repositories must exist and be configured by developer
- **What it does**: Full development + testing + organized Pull Requests
- **Works with**: New projects, existing single repositories, and multi-repository setups
- **Smart PR Features**:
  - Groups features into 3-4 logical, reviewable PRs
  - Foundation setup (auth, database, core infrastructure)
  - Business logic features (split into manageable chunks)
  - API layer and integrations
  - Dependency-aware ordering for review

### Confidence-Building Features
- **Evidence-Based Confidence**: Binary pass/fail testing (no percentage scores that create doubt)
- **Detailed Reporting**: Comprehensive confidence reports with specific metrics and recommendations
- **Developer-Controlled Complexity**: Advanced features are opt-in only

## Project Types Supported

1. **New Projects** (`project_type: "new"`): Creates from scratch with auto-generated testing strategy
2. **Existing Single Repository** (`project_type: "single_repo"`): Adds features to existing codebase, analyzes patterns, respects existing structure
3. **Existing Multi-Repository** (`project_type: "multi_repo"`): Coordinates changes across multiple existing repos with dependency management

All project types support the same three development modes and are fully compatible with PR creation functionality.

## Multi-Repository Support

Agent supports coordinating changes across multiple repositories:
- Features can have `repo_tasks` specifying affected repositories
- Creates separate PR groups for each repository
- Cross-repository dependencies tracked automatically
- Each repository must have GitHub remote configured for PR creation

### Cross-Repository Coordination
- PR descriptions include multi-repo context and dependency information
- Review order respects cross-repository dependencies
- Each PR clearly indicates which other repositories' PRs must be merged first

## Error Handling & Resume

- All phases support interruption and resume via `--resume` flag
- State persisted in `.agent-state.json` after each significant operation
- Failed features don't pollute subsequent feature sessions
- Comprehensive error reporting with troubleshooting guidance

## Prerequisites for Pull Request Creation

To use `--create-smart-prs` (Mode 3), repositories must be set up first:

### Prerequisites Checklist:
- ✅ GitHub repository exists (created by developer)
- ✅ Remote origin configured: `git remote add origin <repo-url>`
- ✅ GitHub CLI authenticated: `gh auth login`

### Verification Commands:
```bash
# Verify Git remote
git remote -v

# Verify GitHub CLI access
gh auth status

# Check current branch
git status
```

**Important**: The agent will NOT create repositories for you. Repository setup is the developer's responsibility.

## Existing Repository Integration

### How Existing Repository Integration Works

**AI-Powered Codebase Analysis:**
- Uses a Claude agent session (Sonnet 4, bounded to 12 turns) with read-only tools to explore the codebase
- Detects architecture patterns, coding conventions (with actual code examples), key abstractions, and module relationships
- Identifies testing frameworks, API patterns, and entry points
- Falls back to deterministic analysis (file extension counting, string matching) if agent fails
- Disable agent analysis with `ANALYSIS_USE_AGENT=false` for faster deterministic-only mode

**Intelligent Integration:**
- New features follow your existing code style
- Tests use your established testing framework
- Maintains consistency with existing patterns
- Preserves existing Git history and branching strategy

## Troubleshooting

### Common Issues and Solutions

**Development stopped unexpectedly:**
```bash
python main.py develop feature_list.json --resume
```

**Want to skip a feature:**
Edit `feature_list.json` and remove the feature, or mark it as completed in `.agent-state.json`.

**Want to re-implement a feature:**
Remove the feature from `features_status` in `.agent-state.json` and run with `--resume`.

**Tests keep failing:**
The agent will iterate to fix failures. If stuck, interrupt (Ctrl+C), fix manually, then `--resume`.

## Integration Points

- **GitHub CLI**: Required for PR creation (`gh auth login`)
- **Git**: Used for branching, committing, PR management
- **AWS Bedrock**: Core Claude model access
- **Project Testing Frameworks**: Auto-detected and integrated (pytest, Jest, JUnit, etc.)