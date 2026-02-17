# Project Init Templates

Choose the template that matches your project type. Each template includes:
1. **Template structure** - Placeholder sections to fill in
2. **Complete example** - A real-world example you can reference

## Templates

| Template | Use When |
|----------|----------|
| `project-init-new.md` | Creating a new project from scratch |
| `project-init-single-repo.md` | Adding features to an existing repository |
| `project-init-multi-repo.md` | Coordinating changes across multiple repositories |

## Usage

1. View the appropriate template to understand the structure
2. Create `project-init.md` in YOUR project folder (not here!)
3. Fill in the sections using the example as reference
4. Run the planning phase

```bash
# View template for reference
cat ~/tools/coding-agent/templates/project-init-new.md

# Create your project folder
mkdir ~/my-projects/my-app
cd ~/my-projects/my-app

# Create your project-init.md
nano project-init.md

# Run planning
python ~/tools/coding-agent/main.py plan ./project-init.md -o .
```

## Key Sections Explained

### Project Type
- `New project (create from scratch)` - Brand new codebase
- `Existing repository (single)` - Add to one existing repo
- `Multi-repository` - Coordinate across multiple repos

### Jira Ticket (for existing repos)
Used in branch naming: `feature/ECOM-456-export-functionality`

### Existing Codebase / Repositories
- Paths must be absolute or relative to where you run the command
- Include key modules so the agent understands the structure
- Specify test commands so the agent can verify its work

### Cross-Repo Dependencies (multi-repo only)
Order in which repositories should be modified. The agent will:
1. Complete all features in upstream repos first
2. Then move to downstream repos

### Requirements
Be specific! The more detail you provide, the better the agent can implement.

Good: "Export user's orders to CSV with columns: order_id, date, total, status"
Bad: "Add export feature"

### Success Criteria
How will you verify the feature works? Include:
- Expected behavior
- Performance requirements
- Test coverage expectations

### Testing Instructions
How should the agent verify its implementation?
- Unit test command
- Integration test command
- Manual verification steps
