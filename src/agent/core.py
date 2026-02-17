"""Main CodingAgent orchestrator."""

import asyncio
import json
import re
from typing import Optional, Literal
from pathlib import Path

from ..models.feature import Feature, FeatureList
from ..models.state import AgentState
from ..services.state_manager import StateManager
from ..services.branch_manager import BranchManager
from ..services.git_manager import GitManager
from ..services.context_tracker import ContextTracker
from ..services.cost_tracker import CostTracker
from .session import AgentSession
from .prompts import PromptTemplates


ExitReason = Literal["completed", "context_full", "error", "interrupted"]


class CodingAgent:
    """Main orchestrator that manages the development loop.

    Implements Feature-Based Sessions: one feature per agent session.
    """

    def __init__(
        self,
        feature_list: FeatureList,
        state_manager: StateManager,
        working_directory: Optional[str] = None,
        feature_list_path: Optional[str] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        """Initialize the coding agent.

        Args:
            feature_list: The feature list to implement
            state_manager: Manager for state persistence
            working_directory: Base working directory
            feature_list_path: Path to feature_list.json for saving status updates
            cost_tracker: Optional CostTracker for recording API costs
        """
        self.feature_list = feature_list
        self.state_manager = state_manager
        self.feature_list_path = feature_list_path
        self.working_directory = working_directory or self._determine_working_dir()

        # Initialize services
        self.context_tracker = ContextTracker()
        self.cost_tracker = cost_tracker or CostTracker()
        self.git_manager = GitManager(self.working_directory)

        # Branch manager for existing repos
        self.branch_manager: Optional[BranchManager] = None
        if feature_list.project_type in ("single_repo", "multi_repo"):
            self.branch_manager = BranchManager(self.working_directory)

    def _determine_working_dir(self) -> str:
        """Determine the working directory based on project type."""
        if self.feature_list.output_directory:
            return self.feature_list.output_directory

        if self.feature_list.repositories:
            # Use first repository path for single/multi repo
            return self.feature_list.repositories[0].path

        return str(Path.cwd())

    def _get_model_info(self) -> str:
        """Get the model being used."""
        from ..config import bedrock_config
        return bedrock_config.model_id

    def _print_session_stats(self, session: AgentSession, feature_id: str) -> None:
        """Print session statistics including context usage and cost."""
        message_count = session.get_message_count()
        tool_calls = session.get_tool_call_count()
        input_tokens = session.get_total_input_tokens()
        output_tokens = session.get_total_output_tokens()

        print(f"\n{'─'*60}")
        print(f"📊 SESSION STATS for {feature_id}")
        print(f"   Messages exchanged: {message_count}")
        print(f"   Tool calls made: {tool_calls}")
        print(f"   Input tokens: {input_tokens:,}")
        print(f"   Output tokens: {output_tokens:,}")

        # Show cost from cost tracker
        self.cost_tracker.print_session_summary(feature_id)

        print(f"{'─'*60}")

    def _save_feature_list(self) -> None:
        """Save feature_list.json with updated statuses."""
        if not self.feature_list_path:
            return

        try:
            with open(self.feature_list_path, "w") as f:
                json.dump(
                    self.feature_list.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                )
        except Exception as e:
            print(f"Warning: Could not save feature list: {e}")

    async def run(self, resume: bool = False) -> ExitReason:
        """Run the development loop.

        Args:
            resume: Whether to resume from existing state

        Returns:
            Reason for exiting the loop
        """
        # Load or create state
        if resume and self.state_manager.exists():
            state = self.state_manager.load()
            if state is None:
                print("Failed to load state, starting fresh")
                state = self._create_initial_state()
            else:
                print(f"Resuming session #{state.context_tracking.session_count + 1}")
                state.context_tracking.session_count += 1

                # Restore cost tracker from saved state
                if state.cost_tracking and state.cost_tracking.records:
                    self.cost_tracker.restore_from_state(
                        state.cost_tracking.model_dump()
                    )
                    print(f"   Restored cost data: {self.cost_tracker.format_cost(self.cost_tracker.total_cost)} from previous sessions")
        else:
            state = self._create_initial_state()

        # For new projects, ensure git is initialized
        if self.feature_list.project_type == "new":
            self._ensure_git_initialized()

        # Ensure branch exists for existing repos
        if self.feature_list.project_type in ("single_repo", "multi_repo"):
            await self._ensure_branch(state)

        # Run development loop
        try:
            exit_reason = await self._development_loop(state)
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            await self._prepare_handoff(state)
            return "interrupted"
        except Exception as e:
            print(f"Error: {e}")
            state.conversation_summary = f"Error occurred: {e}"
            self.state_manager.save(state)
            return "error"

        return exit_reason

    def _create_initial_state(self) -> AgentState:
        """Create initial state for a new run."""
        return self.state_manager.create_new(
            project_init_path="",  # Will be set by CLI
            feature_list_path="",  # Will be set by CLI
            feature_list=self.feature_list,
        )

    def _ensure_git_initialized(self) -> None:
        """Ensure git repository is initialized for new projects."""
        if self.git_manager.is_git_repo():
            print(f"Git repository already initialized in {self.working_directory}")
            return

        print(f"\n🔧 Initializing git repository in {self.working_directory}...")
        success = self.git_manager.init_repo()

        if success:
            print("✓ Git repository initialized")
        else:
            print("⚠️  Warning: Could not initialize git repository")
            print("   Commits will not be created for this project")

    async def _ensure_branch(self, state: AgentState) -> None:
        """Ensure feature branch exists and is checked out."""
        if not self.branch_manager:
            print("Warning: BranchManager not available, skipping branch creation")
            return

        if not self.feature_list.branch_name:
            print("Error: No branch name specified for existing repository project!")
            print("This should not happen - all existing repo projects must use feature branches.")
            return

        if state.branch_created:
            # Branch already created, just checkout
            print(f"Checking out existing branch: {self.feature_list.branch_name}")
            success = self.branch_manager.checkout_branch(self.feature_list.branch_name)
            if not success:
                print(f"Warning: Failed to checkout branch {self.feature_list.branch_name}")
            return

        # Create new branch from latest main/master
        default_branch = self.branch_manager.get_default_branch()
        print(f"Creating feature branch '{self.feature_list.branch_name}' from '{default_branch}'")

        success = self.branch_manager.ensure_branch(
            self.feature_list.branch_name,
            base_branch=default_branch,
        )

        if success:
            state.branch_created = True
            state.branch_name = self.feature_list.branch_name  # Update state
            self.state_manager.save(state)
            print(f"✅ Created and checked out feature branch: {self.feature_list.branch_name}")
        else:
            print(f"❌ ERROR: Could not create branch {self.feature_list.branch_name}")
            print(f"   This is a critical issue for existing repository development!")
            raise Exception(f"Failed to create required feature branch: {self.feature_list.branch_name}")

    async def _development_loop(self, state: AgentState) -> ExitReason:
        """Main development loop - one feature per session.

        Returns the reason for exiting.
        """
        total_features = len(self.feature_list.features)
        session_number = 0

        while True:
            # Get next feature to implement (uses status field from features)
            pending = self.feature_list.get_pending_features()
            completed = self.feature_list.get_completed_features()

            if not pending:
                # All features completed - save cost data to state
                state.phase = "completed"
                self._save_cost_to_state(state)
                self.state_manager.save(state)
                self._save_feature_list()
                print(f"\n{'='*60}")
                print(f"✅ ALL FEATURES COMPLETED!")
                print(f"   Total features: {total_features}")
                print(f"   Total sessions: {session_number}")
                print(f"{'='*60}")
                self.cost_tracker.print_total_summary()
                return "completed"

            session_number += 1

            # Get the highest priority pending feature
            feature = pending[0]

            print(f"\n{'='*60}")
            print(f"📋 FEATURE {len(completed)+1}/{total_features}: {feature.id}")
            print(f"   Name: {feature.name}")
            print(f"   Session #: {session_number}")
            print(f"   Pending: {len(pending)} | Completed: {len(completed)}")
            print(f"{'='*60}")

            # Implement the feature (one session per feature)
            success = await self._implement_feature(feature, state)

            if success:
                print(f"✓ Feature {feature.id} completed")
            else:
                print(f"✗ Feature {feature.id} failed")
                # Continue to next feature rather than stopping

            # Persist cost data after each feature
            self._save_cost_to_state(state)
            self.state_manager.save(state)
            self._save_feature_list()

    def _parse_validation_response(self, response_text: str) -> Optional[dict]:
        """Parse structured validation JSON from Claude's response.

        Looks for a JSON block with "validated" key in the response text.
        Returns the parsed dict, or None if parsing fails.
        """
        # Try to find JSON block in markdown code fence
        json_match = re.search(
            r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL
        )
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                if "validated" in result:
                    return result
            except json.JSONDecodeError:
                pass

        # Fallback: try to find any JSON object with "validated" key
        json_match = re.search(
            r'\{[^{}]*"validated"[^{}]*\}', response_text, re.DOTALL
        )
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    async def _implement_feature(
        self, feature: Feature, state: AgentState
    ) -> bool:
        """Implement a single feature in its own session with validation.

        After implementation, sends a validation prompt to the same session
        asking Claude to verify tests pass and acceptance criteria are met.
        Retries up to max_validation_attempts times on failure.

        Returns True if validated successfully, False otherwise.
        """
        # Mark feature as in progress (both in feature_list and state)
        self.feature_list.update_feature_status(feature.id, "in_progress")
        state.mark_feature_in_progress(feature.id)
        self.state_manager.save(state)
        self._save_feature_list()

        # Get codebase analysis if available
        codebase_analysis = None
        if self.feature_list.repositories:
            repo = self.feature_list.repositories[0]
            codebase_analysis = repo.codebase_analysis

        # Create NEW session for this feature
        print(f"\n{'─'*60}")
        print(f"🆕 CREATING NEW AGENT SESSION for {feature.id}")
        print(f"   Model: {self._get_model_info()}")
        print(f"   Working Dir: {self.working_directory}")
        print(f"{'─'*60}")

        session = AgentSession(
            working_directory=self.working_directory,
            system_prompt=PromptTemplates.get_system_prompt(self.feature_list),
            cost_tracker=self.cost_tracker,
            cost_phase="develop",
            cost_label_prefix=feature.id,
        )

        # Build implementation prompt
        prompt = PromptTemplates.get_feature_implementation_prompt(
            feature=feature,
            feature_list=self.feature_list,
            completed_features=list(state.get_completed_feature_ids()),
            codebase_analysis=codebase_analysis,
            previous_summary=state.conversation_summary,
        )

        # Send to Claude
        print(f"\n📤 Sending implementation request...")
        print(f"   Prompt size: ~{len(prompt):,} chars (~{len(prompt)//4:,} tokens)")
        result = await session.send_message(prompt)

        # Print context usage after initial implementation
        self._print_session_stats(session, feature.id)

        if not result.success:
            # API error — mark as pending so it can be retried
            self.feature_list.update_feature_status(feature.id, "pending")
            state.mark_feature_failed(feature.id, result.error or "Unknown error")
            return False

        # ─── Validation feedback loop ───
        from ..config import agent_config
        max_attempts = agent_config.max_validation_attempts
        validated = False
        last_validation_result = None

        for attempt in range(1, max_attempts + 1):
            state.increment_test_attempts(feature.id)
            print(f"\n🔍 VALIDATION ATTEMPT {attempt}/{max_attempts} for {feature.id}")

            # Send validation prompt to SAME session (preserves full context)
            validation_prompt = PromptTemplates.get_validation_prompt(feature)
            validation_response = await session.send_message(validation_prompt)

            if not validation_response.success:
                print(f"   ❌ Validation request failed: {validation_response.error}")
                last_validation_result = {
                    "validated": False,
                    "issues": [f"Validation API call failed: {validation_response.error}"],
                    "fix_needed": "Validation request failed",
                    "test_output_summary": "",
                }
                continue

            # Parse structured JSON response
            validation_result = self._parse_validation_response(
                validation_response.content
            )

            if validation_result is None:
                print(f"   ⚠️  Could not parse validation response, treating as failed")
                last_validation_result = {
                    "validated": False,
                    "issues": ["Could not parse validation response from agent"],
                    "fix_needed": "Agent did not return structured validation JSON",
                    "test_output_summary": "",
                }
            else:
                last_validation_result = validation_result
                tests_passed = validation_result.get("tests_passed", False)
                is_validated = validation_result.get("validated", False)

                print(f"   Tests passed: {'✅' if tests_passed else '❌'}")
                print(f"   Validated: {'✅' if is_validated else '❌'}")

                if is_validated:
                    validated = True
                    print(f"   ✅ Feature {feature.id} validated successfully!")
                    break

                # Print issues
                issues = validation_result.get("issues", [])
                if issues:
                    print(f"   Issues found:")
                    for issue in issues:
                        print(f"      - {issue}")

            # If not the last attempt, send fix prompt
            if attempt < max_attempts:
                print(f"\n🔧 Sending fix request (attempt {attempt + 1})...")
                fix_prompt = PromptTemplates.get_validation_fix_prompt(
                    feature=feature,
                    validation_result=last_validation_result,
                    attempt_number=attempt + 1,
                )
                fix_response = await session.send_message(fix_prompt)
                if not fix_response.success:
                    print(f"   ❌ Fix request failed: {fix_response.error}")

        # ─── Handle result ───
        self._print_session_stats(session, feature.id)

        if validated:
            self._commit_and_mark_completed(feature, state)
        else:
            print(f"\n❌ Feature {feature.id} failed validation after {max_attempts} attempts")
            error_msg = (
                last_validation_result.get("fix_needed", "Validation failed")
                if last_validation_result
                else "Validation failed"
            )
            self._commit_wip_and_mark_failed(feature, state, error_msg)

        # Update conversation summary for next feature
        summary_prompt = PromptTemplates.get_handoff_summary_prompt()
        summary_result = await session.send_message(summary_prompt)
        if summary_result.success:
            state.conversation_summary = summary_result.content

        return validated

    def _commit_and_mark_completed(
        self, feature: Feature, state: AgentState
    ) -> None:
        """Commit changes and mark feature as completed."""
        if self.git_manager.has_changes():
            commit_result = self.git_manager.create_feature_commit(
                feature_id=feature.id,
                feature_name=feature.name,
                project_name=self.feature_list.project_name,
                jira_ticket=self.feature_list.jira_ticket,
                files=self.git_manager.get_changed_files(),
            )
            if commit_result.success:
                self.feature_list.update_feature_status(feature.id, "completed")
                state.mark_feature_completed(
                    feature.id, commit_hash=commit_result.commit_hash
                )
                print(f"Committed: {commit_result.commit_hash}")
            else:
                print(f"Warning: Commit failed - {commit_result.error_message}")
                self.feature_list.update_feature_status(feature.id, "completed")
                state.mark_feature_completed(feature.id)
        else:
            self.feature_list.update_feature_status(feature.id, "completed")
            state.mark_feature_completed(feature.id)

    def _commit_wip_and_mark_failed(
        self, feature: Feature, state: AgentState, error_message: str
    ) -> None:
        """Commit changes as WIP and mark feature as failed."""
        if self.git_manager.has_changes():
            commit_result = self.git_manager.create_wip_commit(
                feature_id=feature.id,
                feature_name=feature.name,
                project_name=self.feature_list.project_name,
                jira_ticket=self.feature_list.jira_ticket,
                files=self.git_manager.get_changed_files(),
            )
            if commit_result.success:
                print(f"WIP Committed: {commit_result.commit_hash}")
            else:
                print(f"Warning: WIP commit failed - {commit_result.error_message}")

        self.feature_list.update_feature_status(feature.id, "failed")
        state.mark_feature_failed(feature.id, error_message)
        if feature.id in state.features_status:
            state.features_status[feature.id].tests_passed = False

    def _save_cost_to_state(self, state: AgentState) -> None:
        """Persist current cost tracker data into agent state."""
        from ..models.state import CostTracking, CostRecord

        summary = self.cost_tracker.get_summary()
        state.cost_tracking = CostTracking(
            total_input_tokens=summary["total_input_tokens"],
            total_output_tokens=summary["total_output_tokens"],
            total_cost=summary["total_cost"],
            phase_costs=summary["phase_costs"],
            feature_costs=summary["feature_costs"],
            records=[CostRecord(**r) for r in summary["records"]],
        )

    async def _prepare_handoff(self, state: AgentState) -> None:
        """Prepare state for handoff to next session."""
        state.context_tracking.handoff_triggered = True
        state.context_tracking.estimated_tokens_used = self.context_tracker.estimated_tokens
        self._save_cost_to_state(state)

        self.state_manager.save(state)
        print("\nSession handoff prepared. State saved.")
        print(state.get_progress_summary())

    async def implement_single_feature(
        self, feature_id: str, state: Optional[AgentState] = None
    ) -> bool:
        """Implement a specific feature by ID.

        Args:
            feature_id: ID of the feature to implement
            state: Optional existing state

        Returns:
            True if successful
        """
        # Find the feature
        feature = None
        for f in self.feature_list.features:
            if f.id == feature_id:
                feature = f
                break

        if not feature:
            print(f"Feature {feature_id} not found")
            return False

        # Load or create state
        if state is None:
            if self.state_manager.exists():
                state = self.state_manager.load()
            if state is None:
                state = self._create_initial_state()

        # For new projects, ensure git is initialized
        if self.feature_list.project_type == "new":
            self._ensure_git_initialized()

        # Ensure branch
        if self.feature_list.project_type in ("single_repo", "multi_repo"):
            await self._ensure_branch(state)

        # Implement
        return await self._implement_feature(feature, state)
