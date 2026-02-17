# Autonomous Coding Agent

An autonomous coding agent powered by Claude via AWS Bedrock that reads project descriptions and implements features with thorough testing and clean commits.

## Features

- **Three-Phase Workflow**: Plan → Feature → Develop with explicit approval at each step
- **Intelligent Spec Enhancement**: Claude analyzes your requirements and fills in missing details (edge cases, error handling, security, etc.)
- **Feature-Based Sessions**: One Claude agent session per feature for thorough testing
- **Multi-Project Support**: New projects, single repos, or multi-repo coordination
- **Jira Integration**: Automatic feature branch naming from Jira tickets
- **State Persistence**: Resume interrupted sessions seamlessly
- **Codebase Awareness**: Analyzes existing code patterns before implementation
- **Auto-Generated Testing Strategy**: Automatically determines testing approach based on tech stack

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd autonomus-coding-agent-cluade

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Requirements

- Python 3.10+
- AWS credentials configured with Bedrock access

### AWS Configuration

The agent uses Claude models hosted on AWS Bedrock. Configure your AWS credentials:

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# Option 2: AWS CLI profile
aws configure --profile your-profile
export AWS_PROFILE=your-profile

# Optional: Override the default model
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

Ensure your AWS account has Bedrock model access enabled for Claude models.

## Quick Start

```bash
# 1. Create your project folder (OUTSIDE the agent repo)
mkdir ~/my-projects/task-manager
cd ~/my-projects/task-manager

# 2. Create project-init.md in YOUR project folder
# Use templates from the agent repo as reference
cat ~/tools/coding-agent/templates/project-init-new.md  # view template
nano project-init.md  # create your own

# 3. Step 1: Generate project-init-final.md (Claude enhances your spec)
python ~/tools/coding-agent/main.py plan ./project-init.md

# 4. Review project-init-final.md (Claude added missing details, edge cases, etc.)

# 5. Step 2: Generate feature_list.json
python ~/tools/coding-agent/main.py feature ./project-init-final.md

# 6. Review the generated feature_list.json

# 7. Step 3: Start development
python ~/tools/coding-agent/main.py develop ./feature_list.json
```

> **Important**: Never create or modify files inside the agent repository. All your project files (`project-init.md`, `feature_list.json`, source code) should be in YOUR project folder.

---

## User Journey

### Journey 1: Building a New Project from Scratch

**Scenario**: You want to build a Task Manager API with user authentication.

#### Step 1: Set Up Your Project Folder

Create a new folder for YOUR project (not inside the agent repo):

```bash
mkdir ~/my-projects/task-manager
cd ~/my-projects/task-manager
```

#### Step 2: Create Project Description

Create `project-init.md` in your project folder (reference templates from agent repo):

```markdown
# Task Manager API

## Introduction
A REST API for managing tasks with user authentication and team collaboration.

## Project Type
New project (create from scratch)

## Tech Stack
- Language: Python
- Framework: FastAPI
- Database: SQLite
- Authentication: JWT

## Functional Requirements
What the system should DO (user-facing features and behaviors):
- FR-1: User registration and login with JWT tokens
- FR-2: CRUD operations for tasks (create, read, update, delete)
- FR-3: Task assignment to users
- FR-4: Task filtering by status and assignee
- FR-5: Due date tracking with overdue notifications

## System Requirements
Non-functional requirements (performance, security, scalability, etc.):
- SR-1: API response time under 200ms for typical requests
- SR-2: Passwords hashed using bcrypt
- SR-3: Rate limiting: 100 requests per minute per user

## Success Criteria
- All endpoints return proper HTTP status codes
- Authentication protects all task endpoints
- Unit tests cover core functionality
- API documentation auto-generated via OpenAPI
```

> **Note**: The agent will automatically generate the testing strategy based on your tech stack. No need to add a "Testing Instructions" section!

#### Step 3: Generate project-init-final.md (Planning Phase)

Run from your project folder:

```bash
# Assuming agent is installed at ~/tools/coding-agent
python ~/tools/coding-agent/main.py plan ./project-init.md
```

The agent:
1. Parses your project description
2. Validates Functional and System Requirements sections
3. **Uses Claude to intelligently enhance your specification** - filling in:
   - Missing edge cases and error scenarios
   - Security considerations (authentication, input validation)
   - Performance and reliability requirements
   - API contract details and data models
   - Error handling strategies
   - Configuration and integration points
4. Generates testing strategy based on tech stack
5. Creates comprehensive `project-init-final.md` for your review

#### Step 4: Review project-init-final.md

Open `project-init-final.md` and verify:
- Claude's enhancements are appropriate for your project
- All requirements (original + enhanced) are correct
- Edge cases and error scenarios make sense
- Auto-generated testing strategy is appropriate
- Make any adjustments to project-init.md and re-run `plan` if needed

#### Step 5: Generate Feature List

```bash
python ~/tools/coding-agent/main.py feature ./project-init-final.md
```

The agent analyzes your requirements and generates `feature_list.json` in your project folder:

```json
{
  "project_name": "task-manager-api",
  "features": [
    {
      "id": "FEAT-001",
      "name": "Project Setup",
      "description": "Initialize FastAPI project with SQLite database connection",
      "status": "pending"
    },
    {
      "id": "FEAT-002",
      "name": "User Authentication",
      "description": "Implement JWT-based registration and login",
      "status": "pending",
      "depends_on": ["FEAT-001"]
    },
    {
      "id": "FEAT-003",
      "name": "Task CRUD Operations",
      "status": "pending",
      "depends_on": ["FEAT-002"]
    }
  ]
}
```

**Feature Status Values:**
- `pending` - Not yet started
- `in_progress` - Currently being implemented
- `completed` - Successfully implemented and tested

#### Step 6: Review Feature List

Open `feature_list.json` in your project folder and review:
- Are all requirements covered?
- Is the feature order logical?
- Are dependencies correct?

Make any adjustments if needed.

#### Step 7: Start Development

```bash
python ~/tools/coding-agent/main.py develop ./feature_list.json
```

The agent:
1. Creates a new session for FEAT-001
2. Implements the feature
3. Writes tests
4. Runs tests until they pass
5. Commits the changes
6. Moves to FEAT-002 in a fresh session
7. Repeats until all features complete

#### Step 8: Monitor Progress

```bash
python ~/tools/coding-agent/main.py status ./feature_list.json
```

Output:
```
==================================================
Development Status
==================================================
Status: in_progress
Features: 2/5 completed
In Progress: FEAT-003
Sessions: 3
==================================================
```

#### Step 9: Resume if Interrupted

If the process is interrupted (Ctrl+C, connection loss, etc.):

```bash
python ~/tools/coding-agent/main.py develop ./feature_list.json --resume
```

The agent picks up from where it left off.

---

### Journey 2: Adding Features to an Existing Repository

**Scenario**: You have an existing e-commerce API and want to add export functionality.

#### Step 1: Create Project Description

Create `project-init.md` in your existing repo folder (reference template from agent repo):

```bash
cd /path/to/your/ecommerce-api
nano project-init.md
```

```markdown
# Add Export Feature to E-Commerce API

## Introduction
Add CSV and PDF export functionality for orders and customer data.

## Project Type
Existing repository (single)

## Jira Ticket
ECOM-789

## Existing Codebase
- Path: /home/dev/projects/ecommerce-api
- Main entry: src/main.py
- Key modules: src/orders/, src/customers/, src/auth/
- Test location: tests/
- Test command: pytest

## Functional Requirements
What the feature should DO (user-facing behaviors):
- FR-1: Export orders to CSV format with all order details
- FR-2: Export orders to PDF format with company branding
- FR-3: Export customer list to CSV (admin only)
- FR-4: Add date range filtering for exports

## System Requirements
Non-functional requirements (performance, security, compatibility, etc.):
- SR-1: Rate limit export endpoints to 10 requests per minute per user
- SR-2: Export files streamed (not loaded entirely in memory) for large datasets
- SR-3: Maximum export size: 10,000 records per request

## Success Criteria
- Export endpoints follow existing API conventions
- Tests follow existing test patterns
- No breaking changes to existing functionality
```

> **Note**: For existing repos with a testing framework, the agent will detect and use it. If no testing is detected, tests run locally but are NOT committed.

#### Step 2: Generate project-init-final.md

```bash
# Run from your existing repo folder
python ~/tools/coding-agent/main.py plan ./project-init.md --repo .
```

The agent:
1. Parses your project description
2. Analyzes the existing codebase structure
3. Identifies coding patterns (naming conventions, architecture)
4. Detects testing framework and patterns
5. **Uses Claude to enhance your specification** with missing details while respecting existing codebase patterns
6. Creates comprehensive `project-init-final.md` with enhanced requirements and detected codebase info

#### Step 3: Review and Generate Feature List

```bash
# Review project-init-final.md, then generate features
python ~/tools/coding-agent/main.py feature ./project-init-final.md
```

Generated `feature_list.json` includes codebase analysis:

```json
{
  "project_name": "ecom-export-feature",
  "jira_ticket": "ECOM-789",
  "branch_name": "feature/ECOM-789-export-functionality",
  "repositories": [{
    "path": "/home/dev/projects/ecommerce-api",
    "codebase_analysis": {
      "structure": {
        "src/": "Main source code",
        "src/orders/": "Order management module",
        "tests/": "Pytest test files"
      },
      "patterns": {
        "naming": "snake_case for functions, PascalCase for classes",
        "architecture": "Service layer pattern"
      },
      "testing": {
        "framework": "pytest",
        "pattern": "test_*.py files with TestClass structure"
      }
    }
  }],
  "features": [...]
}
```

#### Step 4: Development with Feature Branch

```bash
python ~/tools/coding-agent/main.py develop ./feature_list.json
```

The agent:
1. Creates branch `feature/ECOM-789-export-functionality`
2. Implements each feature following existing patterns
3. Commits with linked messages:

```
feat(FEAT-001): Add CSV export for orders

Part of: ecom-export-feature
Jira: ECOM-789

Files:
- src/orders/export.py
- tests/test_order_export.py

Generated by Autonomous Coding Agent
```

#### Step 5: Review and Merge

After completion:
1. Review the changes on the feature branch
2. Run full test suite: `pytest`
3. Create PR and merge to main

---

### Journey 3: Coordinating Changes Across Multiple Repositories

**Scenario**: Add user activity tracking that spans database, backend, and frontend repos.

#### Step 1: Create Multi-Repo Project Description

Create `project-init.md` in a dedicated folder for this multi-repo project:

```bash
mkdir ~/my-projects/activity-tracking
cd ~/my-projects/activity-tracking
nano project-init.md
```

```markdown
# User Activity Tracking Feature

## Introduction
Track and display user activity across the platform.

## Project Type
Multi-repository

## Jira Ticket
TRACK-456

## Repositories

### 1. Database (PostgreSQL)
- Path: /repos/company-database
- Language: SQL
- Purpose: Schema and migrations
- Test command: psql -f tests/run_tests.sql

### 2. Backend API (Python)
- Path: /repos/backend-api
- Language: Python
- Framework: FastAPI
- Purpose: Activity endpoints
- Test command: pytest

### 3. Frontend Dashboard (TypeScript)
- Path: /repos/frontend-dashboard
- Language: TypeScript
- Framework: React
- Purpose: Activity UI components
- Test command: npm test

## Cross-Repo Dependencies
- Database must be completed before Backend API
- Backend API must be completed before Frontend Dashboard

## Functional Requirements
What the feature should DO:
- FR-1: Database: Create user_activities table with proper indexes
- FR-2: Backend: ActivityController with CRUD + aggregation endpoints
- FR-3: Frontend: ActivityFeed component and ActivityDashboard page

## System Requirements
Non-functional requirements:
- SR-1: Database queries must use indexes for performance
- SR-2: API endpoints must support pagination
- SR-3: Frontend must handle loading states gracefully
```

#### Step 2: Generate project-init-final.md

```bash
python ~/tools/coding-agent/main.py plan ./project-init.md --multi-repo
```

The agent:
1. Analyzes each repository's structure and patterns
2. Detects testing frameworks in each repo
3. **Uses Claude to enhance your specification** considering cross-repo dependencies
4. Creates comprehensive `project-init-final.md` with enhanced requirements and all detected codebase info

#### Step 3: Generate Feature List

```bash
python ~/tools/coding-agent/main.py feature ./project-init-final.md
```

The agent creates features with repo-specific tasks and respects cross-repo dependencies.

#### Step 4: Development Across Repos

```bash
python ~/tools/coding-agent/main.py develop ./feature_list.json
```

The agent:
1. Creates `feature/TRACK-456-activity-tracking` branch in ALL repos
2. Implements database changes first (FEAT-001)
3. Then backend API (FEAT-002)
4. Finally frontend (FEAT-003)
5. Each commit references the Jira ticket

#### Step 5: Coordinated Review

All repos have the same branch name, making it easy to:
1. Review changes across all repos
2. Create linked PRs
3. Merge in dependency order

---

## Command Reference

All commands assume `AGENT_PATH` is where you cloned the agent (e.g., `~/tools/coding-agent`).

### Step 1: Plan (Generate project-init-final.md)

| Command | Description |
|---------|-------------|
| `python $AGENT_PATH/main.py plan <project-init.md>` | Generate project-init-final.md for new project |
| `python $AGENT_PATH/main.py plan <project-init.md> --repo <path>` | Generate for existing repo (analyzes codebase) |
| `python $AGENT_PATH/main.py plan <project-init.md> --multi-repo` | Generate for multiple repos |
| `python $AGENT_PATH/main.py plan <project-init.md> --skip-requirements-validation` | Skip Functional/System Requirements validation |

### Step 2: Feature (Generate feature_list.json)

| Command | Description |
|---------|-------------|
| `python $AGENT_PATH/main.py feature <project-init-final.md>` | Generate feature_list.json |
| `python $AGENT_PATH/main.py feature <project-init-final.md> -o <dir>` | Specify output directory |
| `python $AGENT_PATH/main.py feature <project-init-final.md> --feature-list-output <path>` | Override feature_list.json path |

### Step 3: Develop (Implement features)

| Command | Description |
|---------|-------------|
| `python $AGENT_PATH/main.py develop <feature_list.json>` | Start development |
| `python $AGENT_PATH/main.py develop <feature_list.json> --resume` | Resume interrupted session |
| `python $AGENT_PATH/main.py develop <feature_list.json> --feature FEAT-002` | Implement specific feature |
| `python $AGENT_PATH/main.py status <feature_list.json>` | Show progress |

**Tip**: Add an alias to your shell for convenience:
```bash
alias coding-agent="python ~/tools/coding-agent/main.py"
# Then use: coding-agent plan ./project-init.md
```

## Project Structure

**Agent Repository** (do not modify):
```
autonomus-coding-agent-cluade/
├── main.py                      # CLI entry point
├── requirements.txt             # Dependencies
├── templates/                   # Project init templates (reference only)
│   ├── project-init-new.md
│   ├── project-init-single-repo.md
│   └── project-init-multi-repo.md
└── src/
    ├── models/                  # Pydantic data models
    ├── services/                # Business logic
    ├── agent/                   # Claude Code SDK integration
    └── pipeline/                # Execution pipelines
```

**Your Project Folder** (created by you):
```
~/my-projects/task-manager/
├── project-init.md              # Your project description (you create this)
├── project-init-final.md        # Generated by agent (plan phase) - for review
├── feature_list.json            # Generated by agent (feature phase)
├── .agent-state.json            # Generated by agent (tracks progress)
└── src/                         # Your project source code (created by agent)
```

## How It Works

### Three-Phase Workflow

The agent uses a deliberate three-phase workflow with explicit approval points:

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: PLAN                                                  │
│  python main.py plan project-init.md                            │
│                                                                 │
│  ✓ Parse project description                                    │
│  ✓ Validate Functional/System Requirements                      │
│  ✓ Analyze existing codebase (if applicable)                    │
│  ✓ USE CLAUDE TO ENHANCE SPECIFICATION                          │
│    → Add missing edge cases, error scenarios                    │
│    → Add security/performance/reliability requirements          │
│    → Add API contracts, data models, error handling             │
│  ✓ Generate testing strategy                                    │
│  → Output: COMPREHENSIVE project-init-final.md                  │
│                                                                 │
│  [STOP - Developer reviews enhanced specification]              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: FEATURE                                               │
│  python main.py feature project-init-final.md                   │
│                                                                 │
│  ✓ Use Claude to break down requirements into features          │
│  ✓ Determine feature dependencies                               │
│  ✓ Generate test criteria for each feature                      │
│  → Output: feature_list.json                                    │
│                                                                 │
│  [STOP - Developer reviews feature_list.json]                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: DEVELOP                                               │
│  python main.py develop feature_list.json                       │
│                                                                 │
│  For each feature:                                              │
│  ✓ Create feature branch (if Jira ticket provided)              │
│  ✓ Implement code following detected patterns                   │
│  ✓ Write and run tests                                          │
│  ✓ Iterate until tests pass                                     │
│  ✓ Commit with feature reference                                │
│  → Output: Working code with tests                              │
└─────────────────────────────────────────────────────────────────┘
```

**Why separate phases?**
- **Explicit approval points**: You review before each major step
- **Easy iteration**: Adjust project-init.md and re-run `plan` without regenerating features
- **Transparency**: See exactly what the agent detected and planned before development

### Why Feature-Based Sessions?

Each feature gets its own Claude agent session because:

1. **Testing cycles are context-heavy**: Implement → Test → Fail → Debug → Fix → Retest can consume 85-100% of context
2. **Fresh context = better focus**: Each feature gets full attention without accumulated noise
3. **Error isolation**: A failed feature doesn't pollute the next one
4. **File reading over memory**: Agent reads actual files rather than relying on conversation memory

### State Persistence

Progress is saved to `.agent-state.json`:
- Which features are completed
- Current feature in progress
- Commit hashes for each feature
- Conversation summary for context handoff

This enables seamless resume after interruptions.

### Codebase Analysis

For existing repositories, the agent analyzes:
- Directory structure
- Naming conventions
- Architecture patterns
- Testing framework and patterns
- Dependencies

This ensures new code matches existing style.

### Auto-Generated Testing Strategy

The agent automatically determines the testing strategy based on:

**For new projects** (based on tech stack):
| Language | Framework | Test Command |
|----------|-----------|--------------|
| Python | pytest | `pytest tests/ -v` |
| TypeScript/JavaScript | Jest | `npm test` |
| Java | JUnit 5 | `mvn test` |
| Go | go test | `go test ./...` |

**For existing repositories**:
- If testing framework detected: Uses existing patterns, commits tests
- If no testing detected: Tests run locally but are NOT committed to feature branch

This is shown in `project-init-final.md` under "Testing Strategy (Auto-Generated)".

### Intelligent Specification Enhancement

The `plan` phase uses Claude to intelligently analyze your project-init.md and enhance it with comprehensive software development details. This addresses a common problem: **developers often write minimal specifications**, assuming the agent will figure out the details.

**What Claude adds to your specification:**

| Category | What Claude Fills In |
|----------|---------------------|
| **Functional Requirements** | Breaks down high-level requirements, adds acceptance criteria, edge cases |
| **System Requirements** | Performance targets, security considerations, reliability requirements |
| **API Contracts** | Endpoint specs, request/response schemas, status codes, error formats |
| **Data Models** | Entity relationships, validation rules, index requirements |
| **Error Handling** | Error categories, user-facing messages, logging requirements |
| **Configuration** | Environment configs, secrets management, feature flags |
| **Integration Points** | External dependencies, retry strategies, failure handling |

**Example transformation:**

Your input (minimal):
```markdown
## Functional Requirements
- FR-1: Users can create TODO items
- FR-2: Users can mark items as complete
```

Claude's enhancement:
```markdown
## Functional Requirements

### Core Features
- FR-1: Users can create TODO items
  - Acceptance: Item created with title, optional description, creation timestamp
  - Edge Cases: Empty title rejected, maximum title length enforced
- FR-2: Users can mark items as complete
  - Acceptance: Status changes to "completed", completion timestamp recorded
  - Edge Cases: Already completed items remain completed

### Error Scenarios
- FR-ERR-1: Invalid input returns 400 with descriptive error message
- FR-ERR-2: Non-existent item returns 404
```

This ensures the feature generation phase receives a **complete specification**, leading to better feature breakdown and fewer assumptions during development.

## Troubleshooting

**Q: Development stopped unexpectedly**
```bash
python main.py develop feature_list.json --resume
```

**Q: Want to skip a feature**
Edit `feature_list.json` and remove the feature, or mark it as completed in `.agent-state.json`.

**Q: Want to re-implement a feature**
Remove the feature from `features_status` in `.agent-state.json` and run with `--resume`.

**Q: Tests keep failing**
The agent will iterate to fix failures. If stuck, interrupt (Ctrl+C), fix manually, then `--resume`.

## License

MIT
