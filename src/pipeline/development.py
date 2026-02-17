"""Development pipeline - implements features from feature list."""

import json
from pathlib import Path
from typing import Optional

from ..models.feature import FeatureList
from ..models.state import AgentState
from ..models.testing import ComprehensiveTestReport
from ..models.pull_request import SmartPRPlan
from ..services.state_manager import StateManager
from ..services.comprehensive_tester import ComprehensiveTester
from ..services.smart_pr_manager import SmartPRManager
from ..services.git_manager import GitManager
from ..services.branch_manager import BranchManager
from ..services.cost_tracker import CostTracker
from ..agent.core import CodingAgent, ExitReason
from ..agent.session import AgentSession
from .planning import load_feature_list


class DevelopmentPipeline:
    """Orchestrates the development phase to implement features."""

    def __init__(
        self,
        feature_list_path: str,
        resume: bool = False,
        feature_id: Optional[str] = None,
        comprehensive_testing: bool = False,
        create_smart_prs: bool = False,
    ):
        """Initialize development pipeline.

        Args:
            feature_list_path: Path to feature_list.json
            resume: Whether to resume from existing state
            feature_id: Specific feature to implement (optional)
            comprehensive_testing: Whether to generate comprehensive test suites
            create_smart_prs: Whether to create smart Pull Requests
        """
        self.feature_list_path = Path(feature_list_path)
        self.resume = resume
        self.feature_id = feature_id
        self.comprehensive_testing = comprehensive_testing
        self.create_smart_prs = create_smart_prs

        self.feature_list: Optional[FeatureList] = None
        self.state_manager: Optional[StateManager] = None
        self.cost_tracker = CostTracker()

    def load_feature_list(self) -> FeatureList:
        """Load the feature list from JSON."""
        self.feature_list = load_feature_list(str(self.feature_list_path))
        return self.feature_list

    def get_working_directory(self) -> str:
        """Determine the working directory."""
        if not self.feature_list:
            raise ValueError("Must call load_feature_list() first")

        if self.feature_list.output_directory:
            # New project - use output directory
            return self.feature_list.output_directory

        if self.feature_list.repositories:
            # Existing repo - use first repository path
            return self.feature_list.repositories[0].path

        # Fallback to directory containing feature_list.json
        return str(self.feature_list_path.parent)

    def setup_state_manager(self) -> StateManager:
        """Set up the state manager."""
        working_dir = self.get_working_directory()
        self.state_manager = StateManager(working_dir=working_dir)
        return self.state_manager

    async def run(self) -> ExitReason:
        """Run the development pipeline with optional comprehensive testing and smart PRs.

        Returns:
            Exit reason from the agent
        """
        # Load feature list
        print(f"Loading feature list from: {self.feature_list_path}")
        self.load_feature_list()

        print(f"Project: {self.feature_list.project_name}")  # type: ignore
        print(f"Features: {len(self.feature_list.features)}")  # type: ignore

        # Check if comprehensive features are enabled
        if self.comprehensive_testing:
            print("🧪 Comprehensive testing enabled")
        if self.create_smart_prs:
            print("📋 Smart PR creation enabled")

        # Setup state
        self.setup_state_manager()

        # Update state with new feature flags
        state = self.state_manager.load()  # type: ignore
        if state:
            state.comprehensive_testing_enabled = self.comprehensive_testing
            state.smart_prs_enabled = self.create_smart_prs
            self.state_manager.save(state)  # type: ignore

        # Determine working directory
        working_dir = self.get_working_directory()
        print(f"Working directory: {working_dir}")

        # Ensure directory exists for new projects
        if self.feature_list.project_type == "new" and self.feature_list.output_directory:  # type: ignore
            Path(self.feature_list.output_directory).mkdir(parents=True, exist_ok=True)  # type: ignore

        # Create the coding agent
        agent = CodingAgent(
            feature_list=self.feature_list,  # type: ignore
            state_manager=self.state_manager,  # type: ignore
            working_directory=working_dir,
            feature_list_path=str(self.feature_list_path),
            cost_tracker=self.cost_tracker,
        )

        # Run development
        if self.feature_id:
            # Implement specific feature (no comprehensive features for single feature)
            print(f"\nImplementing feature: {self.feature_id}")
            success = await agent.implement_single_feature(self.feature_id)
            return "completed" if success else "error"
        else:
            # Implement all features with enhanced pipeline
            print("\nStarting enhanced development pipeline...")
            return await self._run_enhanced_development(agent, working_dir)

    async def _run_enhanced_development(self, agent: CodingAgent, working_dir: str) -> ExitReason:
        """Run enhanced development with comprehensive testing and smart PRs."""

        # Step 1: Run standard feature development
        print("🔨 Starting feature development...")
        exit_reason = await agent.run(resume=self.resume)

        if exit_reason != "completed":
            print(f"❌ Feature development failed with reason: {exit_reason}")
            return exit_reason

        # Get completed features
        state = self.state_manager.load()  # type: ignore
        if not state:
            print("❌ No state found after development")
            return "error"

        # Get completed features directly from feature_list (more reliable than state)
        completed_features = self.feature_list.get_completed_features()  # type: ignore

        print(f"✅ Completed {len(completed_features)} features")

        # Step 2: Generate comprehensive tests if requested
        if self.comprehensive_testing:
            try:
                await self._run_comprehensive_testing(completed_features, working_dir, agent)
            except Exception as e:
                print(f"❌ Comprehensive testing failed: {e}")
                return "error"

        # Step 3: Create smart PRs if requested
        if self.create_smart_prs:
            try:
                await self._create_smart_prs(completed_features, working_dir)
            except Exception as e:
                print(f"❌ Smart PR creation failed: {e}")
                return "error"

        # Step 4: Generate final confidence report
        self._generate_final_confidence_report(state, completed_features, working_dir)

        print("🎉 Development pipeline completed successfully!")
        return "completed"

    async def _run_comprehensive_testing(self, completed_features, working_dir: str, agent: CodingAgent):
        """Run comprehensive testing suite."""
        print("\n" + "="*60)
        print("🧪 COMPREHENSIVE TESTING PHASE")
        print("="*60)

        # Create agent session for test generation
        agent_session = AgentSession(
            working_directory=working_dir,
            cost_tracker=self.cost_tracker,
            cost_phase="develop",
            cost_label_prefix="comprehensive_testing",
        )

        # Create comprehensive tester
        tester = ComprehensiveTester(working_dir)

        # Generate and run comprehensive tests
        from ..utils.file_naming import extract_base_name
        base_name = extract_base_name(str(self.feature_list_path))
        test_report = await tester.create_comprehensive_tests(
            completed_features=completed_features,
            feature_list=self.feature_list,  # type: ignore
            agent_session=agent_session,
            base_name=base_name
        )

        # Check if all tests passed
        if not test_report.all_tests_pass:
            raise Exception(f"Comprehensive tests failed: {test_report.total_passed}/{test_report.total_tests} passed")

        print(f"✅ All {test_report.total_tests} comprehensive tests passed!")
        print(f"   • Individual: {len(test_report.individual_tests)} suites")
        print(f"   • Integration: {test_report.integration_tests.total_tests if test_report.integration_tests else 0} tests")
        print(f"   • End-to-End: {test_report.e2e_tests.total_tests if test_report.e2e_tests else 0} tests")
        print(f"   • Stress: {test_report.stress_tests.total_tests if test_report.stress_tests else 0} tests")
        print(f"   • Failure: {test_report.failure_tests.total_tests if test_report.failure_tests else 0} tests")

        # Update state with test report path
        state = self.state_manager.load()  # type: ignore
        if state:
            from ..utils.file_naming import generate_report_filename
            report_filename = generate_report_filename(str(self.feature_list_path), "comprehensive-test-report")
            state.comprehensive_test_report = str(Path(working_dir) / report_filename)
            self.state_manager.save(state)  # type: ignore

    async def _create_smart_prs(self, completed_features, working_dir: str):
        """Create smart Pull Requests."""
        print("\n" + "="*60)
        print("📋 SMART PR CREATION PHASE")
        print("="*60)

        # Create necessary services (simplified initialization)
        git_manager = GitManager(working_dir)
        branch_manager = BranchManager(working_dir)

        # Create Smart PR Manager
        pr_manager = SmartPRManager(working_dir, git_manager, branch_manager)

        # Create PR plan
        from ..utils.file_naming import extract_base_name
        base_name = extract_base_name(str(self.feature_list_path))
        pr_plan = pr_manager.create_smart_pr_plan(completed_features, self.feature_list, base_name)  # type: ignore

        print(f"📋 Created plan for {len(pr_plan.pr_groups)} Pull Requests:")
        for i, pr_group in enumerate(pr_plan.pr_groups, 1):
            print(f"   {i}. {pr_group.name} ({len(pr_group.features)} features, ~{pr_group.estimated_review_time}min)")

        # Create the actual PRs
        pr_result = await pr_manager.create_pull_requests(pr_plan, self.feature_list)  # type: ignore

        if not pr_result.all_created_successfully:
            raise Exception(f"Failed to create {len(pr_result.failed_prs)} PRs: {pr_result.failed_prs}")

        print(f"✅ Successfully created {len(pr_result.created_prs)} Pull Requests")
        for i, pr_url in enumerate(pr_result.created_prs, 1):
            print(f"   {i}. {pr_url}")

        # Update state with PR info
        state = self.state_manager.load()  # type: ignore
        if state:
            from ..utils.file_naming import generate_report_filename
            pr_plan_filename = generate_report_filename(str(self.feature_list_path), "smart-pr-plan")
            state.smart_pr_plan = str(Path(working_dir) / pr_plan_filename)
            state.created_prs = pr_result.created_prs
            self.state_manager.save(state)  # type: ignore

    def _generate_final_confidence_report(self, state: AgentState, completed_features, working_dir: str):
        """Generate final confidence report."""
        print("\n" + "="*70)
        print("📊 FINAL CONFIDENCE REPORT")
        print("="*70)

        # Load test report if available
        test_report = None
        if state.comprehensive_test_report:
            try:
                with open(state.comprehensive_test_report, 'r') as f:
                    test_data = json.load(f)
                    test_report = ComprehensiveTestReport(**test_data)
            except Exception:
                pass

        # Load PR plan if available
        pr_plan = None
        if state.smart_pr_plan:
            try:
                with open(state.smart_pr_plan, 'r') as f:
                    pr_data = json.load(f)
                    pr_plan = SmartPRPlan(**pr_data)
            except Exception:
                pass

        # Display confidence summary
        confidence_level = "🟢 HIGH CONFIDENCE" if (
            test_report and test_report.all_tests_pass and
            test_report.confidence_level == "high"
        ) else "🟡 MEDIUM CONFIDENCE"

        print(f"🎯 FINAL CONFIDENCE LEVEL: {confidence_level}")
        print(f"📋 PROJECT: {self.feature_list.project_name}")  # type: ignore
        print(f"✅ FEATURES COMPLETED: {len(completed_features)}")

        if test_report:
            print(f"\n🧪 COMPREHENSIVE TESTING:")
            print(f"   ✅ Total Tests: {test_report.total_tests}")
            print(f"   ✅ Tests Passed: {test_report.total_passed}")
            print(f"   ✅ Success Rate: 100%" if test_report.all_tests_pass else f"   ❌ Success Rate: {(test_report.total_passed/test_report.total_tests)*100:.1f}%")

        if pr_plan:
            print(f"\n📋 SMART PULL REQUESTS:")
            print(f"   ✅ PRs Created: {len(pr_plan.pr_groups)}")
            print(f"   ✅ Total Review Time: ~{pr_plan.total_estimated_review_time} minutes")
            print(f"   ✅ Average PR Size: {pr_plan.average_pr_size:.1f} features per PR")

        if state.created_prs:
            print(f"\n🔗 PULL REQUEST URLS:")
            for i, pr_url in enumerate(state.created_prs, 1):
                print(f"   {i}. {pr_url}")

        # Cost breakdown
        if self.cost_tracker.entries:
            self.cost_tracker.print_total_summary()

        print(f"\n🚀 DEPLOYMENT READINESS: {'✅ PRODUCTION READY' if confidence_level.startswith('🟢') else '🟡 REVIEW RECOMMENDED'}")
        print("="*70)

    def get_status(self) -> dict:
        """Get current development status.

        Returns:
            Status dictionary with progress info
        """
        if not self.state_manager:
            self.load_feature_list()
            self.setup_state_manager()

        state = self.state_manager.load()  # type: ignore

        if not state:
            return {
                "status": "not_started",
                "features_total": len(self.feature_list.features) if self.feature_list else 0,  # type: ignore
                "features_completed": 0,
                "features_in_progress": None,
            }

        completed = state.get_completed_feature_ids()
        in_progress = state.get_in_progress_feature_id()

        return {
            "status": state.phase,
            "features_total": len(self.feature_list.features) if self.feature_list else 0,  # type: ignore
            "features_completed": len(completed),
            "features_in_progress": in_progress,
            "session_count": state.context_tracking.session_count,
            "branch": state.branch_name,
        }


async def run_development(
    feature_list_path: str,
    resume: bool = False,
    feature_id: Optional[str] = None,
    comprehensive_testing: bool = False,
    create_smart_prs: bool = False,
) -> ExitReason:
    """Convenience function to run development pipeline.

    Args:
        feature_list_path: Path to feature_list.json
        resume: Whether to resume from existing state
        feature_id: Specific feature to implement
        comprehensive_testing: Whether to generate comprehensive test suites
        create_smart_prs: Whether to create smart Pull Requests

    Returns:
        Exit reason
    """
    pipeline = DevelopmentPipeline(
        feature_list_path=feature_list_path,
        resume=resume,
        feature_id=feature_id,
        comprehensive_testing=comprehensive_testing,
        create_smart_prs=create_smart_prs,
    )
    return await pipeline.run()
