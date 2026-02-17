# Autonomous Coding Agent

An autonomous coding agent powered by Claude (via AWS Bedrock) that reads project descriptions and implements features autonomously. It follows a three-phase workflow — **Plan, Feature, Develop** — with explicit developer approval at each step.

## Features

- **Three-Phase Workflow**: Plan → Feature → Develop with review points between each phase
- **Intelligent Spec Enhancement**: Claude analyzes your requirements and fills in missing details (edge cases, error handling, security, API contracts, etc.)
- **Feature-Based Sessions**: Each feature gets its own isolated Claude session to avoid context pollution
- **AI-Powered Codebase Analysis**: For existing repos, an agent session explores your codebase to understand architecture, patterns, and conventions
- **Cost Tracking**: Real-time token usage and cost tracking across all phases
- **State Persistence**: Resume interrupted sessions seamlessly with `--resume`
- **Comprehensive Testing** (opt-in): Integration, e2e, stress, and failure scenario tests
- **Smart PR Creation** (opt-in): Groups features into logical, reviewable Pull Requests

## Supported Project Types

| Type | Description |
|------|-------------|
| **New Project** | Create from scratch with auto-generated testing strategy |
| **Single Repository** | Add features to an existing codebase, respecting existing patterns |
| **Multi-Repository** | Coordinate changes across multiple repos with dependency management |

## Installation

```bash
git clone https://github.com/prashbor/autonomus-coding-agent-cluade.git
cd autonomus-coding-agent-cluade

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Requirements

- Python 3.10+
- AWS credentials with Bedrock access to Claude models
- For PR creation (optional): GitHub CLI (`gh`) authenticated

### AWS Configuration

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# Option 2: AWS CLI profile
aws configure --profile your-profile
export AWS_PROFILE=your-profile
```

Ensure your AWS account has Bedrock model access enabled for Claude models.

## Quick Start

```bash
# Create your project folder (outside the agent repo)
mkdir ~/my-projects/task-manager && cd ~/my-projects/task-manager

# Create project-init.md (see templates/ for reference)
nano project-init.md

# Step 1: Plan — generates project-init-final.md
python ~/path/to/agent/main.py plan ./project-init.md

# Step 2: Feature — generates feature_list.json
python ~/path/to/agent/main.py feature ./project-init-final.md

# Step 3: Develop — implements all features
python ~/path/to/agent/main.py develop ./feature_list.json
```

> **Important**: All your project files should be in YOUR project folder, not inside the agent repository.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: PLAN                                              │
│  python main.py plan project-init.md                        │
│                                                             │
│  - Parse project description                                │
│  - Analyze existing codebase (if applicable)                │
│  - Claude enhances specification with missing details       │
│  - Generate testing strategy                                │
│  → Output: project-init-final.md                            │
│                                                             │
│  [STOP — Developer reviews enhanced specification]          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: FEATURE                                           │
│  python main.py feature project-init-final.md               │
│                                                             │
│  - Break down requirements into features                    │
│  - Determine dependencies and ordering                      │
│  - Generate test criteria per feature                       │
│  → Output: feature_list.json                                │
│                                                             │
│  [STOP — Developer reviews feature list]                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: DEVELOP                                           │
│  python main.py develop feature_list.json                   │
│                                                             │
│  For each feature (in its own Claude session):              │
│  - Implement code following detected patterns               │
│  - Write and run tests                                      │
│  - Iterate until tests pass                                 │
│  - Commit with feature reference                            │
│  → Output: Working code with tests                          │
└─────────────────────────────────────────────────────────────┘
```

### Why Feature-Based Sessions?

Each feature gets its own Claude agent session because:

1. **Testing cycles are context-heavy**: Implement → Test → Debug → Fix → Retest can consume 85-100% of context
2. **Fresh context = better focus**: Each feature gets full attention without accumulated noise
3. **Error isolation**: A failed feature doesn't pollute the next one

## Development Modes

### Mode 1: Local Development (Default)

```bash
python main.py develop feature_list.json
```

Implements features locally. Works for new projects and existing repos.

### Mode 2: With Comprehensive Testing

```bash
python main.py develop feature_list.json --comprehensive-testing
```

Adds integration tests, e2e workflow tests, stress tests, and failure scenario tests beyond individual feature tests.

### Mode 3: Production Ready

```bash
python main.py develop feature_list.json --comprehensive-testing --create-smart-prs
```

Full development + testing + organized Pull Requests. Groups features into 3-4 logical, reviewable PRs with dependency-aware ordering. Requires GitHub CLI (`gh`) authenticated and repositories with remotes configured.

## Command Reference

### Plan

| Command | Description |
|---------|-------------|
| `python main.py plan <project-init.md>` | Generate enhanced specification |
| `python main.py plan <project-init.md> --repo <path>` | Analyze existing repo first |
| `python main.py plan <project-init.md> --multi-repo` | Multi-repository mode |
| `python main.py plan <project-init.md> --skip-requirements-validation` | Skip requirements validation |

### Feature

| Command | Description |
|---------|-------------|
| `python main.py feature <project-init-final.md>` | Generate feature list |
| `python main.py feature <project-init-final.md> -o <dir>` | Specify output directory |
| `python main.py feature <project-init-final.md> --feature-list-output <path>` | Custom output path |

### Develop

| Command | Description |
|---------|-------------|
| `python main.py develop <feature_list.json>` | Start development |
| `python main.py develop <feature_list.json> --resume` | Resume interrupted session |
| `python main.py develop <feature_list.json> --feature FEAT-002` | Implement specific feature |
| `python main.py develop <feature_list.json> --comprehensive-testing` | Add comprehensive tests |
| `python main.py develop <feature_list.json> --create-smart-prs` | Create organized PRs |

### Status & Reporting

| Command | Description |
|---------|-------------|
| `python main.py status <feature_list.json>` | Show development progress |
| `python main.py confidence-report <feature_list.json>` | Generate confidence report |

## Configuration

### Models

Default model is Claude Opus 4.6. Override via environment variable:

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

Available models:

| Model | ID | Use Case |
|-------|----|----------|
| Opus 4.6 | `us.anthropic.claude-opus-4-6-v1` | Default (most capable) |
| Opus 4.5 | `us.anthropic.claude-opus-4-5-20251101-v1:0` | Alternative |
| Sonnet 4.5 | `us.anthropic.claude-sonnet-4-5-20250514-v1:0` | Codebase analysis (default) |
| Sonnet 4 | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Faster/cheaper |
| Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20250514-v1:0` | Budget option |

### Agent Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MAX_TURNS` | 50 | Max turns per agent session |
| `CONTEXT_THRESHOLD` | 0.75 | Context usage threshold for handoff |
| `MAX_CONTEXT_TOKENS` | 200000 | Max context tokens |
| `MAX_VALIDATION_ATTEMPTS` | 3 | Max test-fix iterations per feature |

### Codebase Analysis Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYSIS_MODEL_ID` | Sonnet 4.5 | Model for analysis sessions |
| `ANALYSIS_MAX_TURNS` | 12 | Max turns per analysis session |
| `ANALYSIS_USE_AGENT` | true | Set `false` for deterministic-only analysis |
| `ANALYSIS_MAX_TREE_DEPTH` | 4 | File tree depth for initial context |

## Generated Files

The agent creates these files in your project directory (not in the agent repo):

| File | Created By | Purpose |
|------|-----------|---------|
| `project-init-final.md` | Plan phase | Enhanced specification for review |
| `feature_list.json` | Feature phase | Feature breakdown with dependencies |
| `.agent-state.json` | Develop phase | Progress tracking (enables resume) |
| `comprehensive_test_report.json` | `--comprehensive-testing` | Test results |
| `smart_pr_plan.json` | `--create-smart-prs` | PR organization plan |

## Troubleshooting

**Development stopped unexpectedly:**
```bash
python main.py develop feature_list.json --resume
```

**Skip a feature:**
Edit `feature_list.json` and remove the feature, or mark it as completed in `.agent-state.json`.

**Re-implement a feature:**
Remove the feature from `features_status` in `.agent-state.json` and run with `--resume`.

**Tests keep failing:**
The agent iterates to fix failures. If stuck, interrupt (Ctrl+C), fix manually, then `--resume`.

## License

MIT
