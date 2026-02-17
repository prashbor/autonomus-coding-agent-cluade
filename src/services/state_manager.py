"""Manage agent state persistence."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.state import AgentState, RepositoryStatus, ContextTracking
from ..models.feature import FeatureList


class StateManager:
    """Manages persistence of agent state to JSON files."""

    DEFAULT_STATE_FILENAME = ".agent-state.json"

    def __init__(self, state_path: Optional[str] = None, working_dir: Optional[str] = None):
        """Initialize state manager.

        Args:
            state_path: Explicit path to state file
            working_dir: Working directory (state file will be created here)
        """
        if state_path:
            self.state_path = Path(state_path)
        elif working_dir:
            self.state_path = Path(working_dir) / self.DEFAULT_STATE_FILENAME
        else:
            self.state_path = Path.cwd() / self.DEFAULT_STATE_FILENAME

    def exists(self) -> bool:
        """Check if state file exists."""
        return self.state_path.exists()

    def load(self) -> Optional[AgentState]:
        """Load state from file.

        Returns None if file doesn't exist.
        """
        if not self.exists():
            return None

        try:
            content = self.state_path.read_text()
            data = json.loads(content)
            return AgentState.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Failed to load state file: {e}")
            return None

    def save(self, state: AgentState) -> None:
        """Save state to file."""
        state.updated_at = datetime.now()

        # Convert to JSON-serializable dict
        data = state.model_dump(mode="json")

        # Write with pretty formatting
        self.state_path.write_text(json.dumps(data, indent=2, default=str))

    def create_new(
        self,
        project_init_path: str,
        feature_list_path: str,
        feature_list: FeatureList,
    ) -> AgentState:
        """Create a new state from feature list."""
        session_id = f"agent-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

        # Build repository status for multi-repo projects
        repositories_status = {}
        if feature_list.project_type in ("single_repo", "multi_repo"):
            for repo in feature_list.repositories:
                repositories_status[repo.id] = RepositoryStatus(
                    path=repo.path,
                    branch_created=False,
                    current_branch=None,
                    last_commit=None,
                )

        state = AgentState(
            session_id=session_id,
            project_init_path=project_init_path,
            feature_list_path=feature_list_path,
            project_type=feature_list.project_type,  # type: ignore
            output_directory=feature_list.output_directory,
            jira_ticket=feature_list.jira_ticket,
            branch_name=feature_list.branch_name,
            branch_created=False,
            repositories_status=repositories_status,
            phase="development",
            features_status={},
            context_tracking=ContextTracking(),
            conversation_summary=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.save(state)
        return state

    def load_or_create(
        self,
        project_init_path: str,
        feature_list_path: str,
        feature_list: FeatureList,
    ) -> AgentState:
        """Load existing state or create new one."""
        existing = self.load()
        if existing:
            return existing
        return self.create_new(project_init_path, feature_list_path, feature_list)

    def delete(self) -> bool:
        """Delete the state file.

        Returns True if deleted, False if didn't exist.
        """
        if self.exists():
            self.state_path.unlink()
            return True
        return False

    def backup(self) -> Optional[Path]:
        """Create a backup of the state file.

        Returns path to backup file, or None if original doesn't exist.
        """
        if not self.exists():
            return None

        backup_path = self.state_path.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        backup_path.write_text(self.state_path.read_text())
        return backup_path

    def update_session_count(self, state: AgentState) -> None:
        """Increment session count and save."""
        state.context_tracking.session_count += 1
        self.save(state)

    def update_branch_created(
        self, state: AgentState, repo_id: Optional[str] = None
    ) -> None:
        """Mark branch as created."""
        if repo_id and repo_id in state.repositories_status:
            state.repositories_status[repo_id].branch_created = True
            state.repositories_status[repo_id].current_branch = state.branch_name
        else:
            state.branch_created = True

        self.save(state)

    def update_conversation_summary(self, state: AgentState, summary: str) -> None:
        """Update conversation summary for handoff."""
        state.conversation_summary = summary
        self.save(state)

    def set_phase_completed(self, state: AgentState) -> None:
        """Mark the project as completed."""
        state.phase = "completed"
        self.save(state)
