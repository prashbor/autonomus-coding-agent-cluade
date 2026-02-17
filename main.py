#!/usr/bin/env python3
"""Autonomous Coding Agent - CLI Entry Point.

A CLI tool that reads project descriptions and autonomously implements features
using Claude Code SDK with thorough testing and clean commits.

Usage:
    # Step 1: Plan phase - generate project-init-final.md for review
    python main.py plan project-init.md
    python main.py plan project-init.md --repo /path/to/existing/repo
    python main.py plan project-init.md --multi-repo

    # Step 2: Feature phase - generate feature_list.json from approved project-init-final.md
    python main.py feature project-init-final.md
    python main.py feature project-init-final.md -o ./output/my-project

    # Step 3: Develop phase - implement features
    python main.py develop feature_list.json
    python main.py develop feature_list.json --resume
    python main.py develop feature_list.json --feature FEAT-002
    python main.py develop feature_list.json --comprehensive-testing --create-smart-prs

    # Additional commands
    python main.py status feature_list.json
    python main.py confidence-report feature_list.json
"""

import argparse
import asyncio
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="autonomous-coding-agent",
        description="Autonomous coding agent that implements features from project descriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Plan command - Step 1: Generate project-init-final.md
    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate project-init-final.md for developer review",
        description="Parse project-init.md, analyze codebase (if existing), and generate project-init-final.md",
    )
    plan_parser.add_argument(
        "project_init",
        type=str,
        help="Path to project-init.md file",
    )
    plan_parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Path to existing repository (single repo mode)",
    )
    plan_parser.add_argument(
        "--multi-repo",
        action="store_true",
        help="Enable multi-repository mode",
    )
    plan_parser.add_argument(
        "--skip-requirements-validation",
        action="store_true",
        help="Skip validation of Functional/System Requirements sections (use legacy format)",
    )

    # Feature command - Step 2: Generate feature_list.json
    feature_parser = subparsers.add_parser(
        "feature",
        help="Generate feature_list.json from project-init-final.md",
        description="Read approved project-init-final.md and generate feature_list.json using Claude",
    )
    feature_parser.add_argument(
        "project_init_final",
        type=str,
        help="Path to project-init-final.md file",
    )
    feature_parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory for new projects",
    )
    feature_parser.add_argument(
        "--feature-list-output",
        type=str,
        default=None,
        help="Override path for feature_list.json output",
    )

    # Develop command
    develop_parser = subparsers.add_parser(
        "develop",
        help="Implement features from feature list",
        description="Load feature_list.json and implement features",
    )
    develop_parser.add_argument(
        "feature_list",
        type=str,
        help="Path to feature_list.json file",
    )
    develop_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing state",
    )
    develop_parser.add_argument(
        "--feature",
        type=str,
        default=None,
        help="Implement specific feature by ID (e.g., FEAT-002)",
    )
    develop_parser.add_argument(
        "--comprehensive-testing",
        action="store_true",
        help="Generate and run comprehensive test suites (integration, e2e, stress, failure scenarios)",
    )
    develop_parser.add_argument(
        "--create-smart-prs",
        action="store_true",
        help="Group features into 3-4 logical Pull Requests for easier review (requires existing GitHub repo)",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show development status",
        description="Show current progress and state",
    )
    status_parser.add_argument(
        "feature_list",
        type=str,
        help="Path to feature_list.json file",
    )

    # Confidence report command
    confidence_parser = subparsers.add_parser(
        "confidence-report",
        help="Generate comprehensive confidence report",
        description="Generate detailed confidence report for completed development",
    )
    confidence_parser.add_argument(
        "feature_list",
        type=str,
        help="Path to feature_list.json file",
    )

    return parser


async def run_plan(args: argparse.Namespace) -> int:
    """Run the planning phase - generates project-init-final.md only."""
    from src.pipeline.planning import PlanningPipeline
    from src.services.cost_tracker import CostTracker

    # Validate inputs
    project_init_path = Path(args.project_init)
    if not project_init_path.exists():
        print(f"Error: File not found: {args.project_init}")
        return 1

    # Create cost tracker for this phase
    cost_tracker = CostTracker()

    # Create pipeline
    pipeline = PlanningPipeline(
        project_init_path=str(project_init_path),
        repo_path=args.repo,
        multi_repo=args.multi_repo,
        cost_tracker=cost_tracker,
    )

    try:
        # Run planning phase 1 - generate project-init-final.md
        final_path = await pipeline.run_plan_phase(
            skip_requirements_validation=args.skip_requirements_validation,
        )

        # Print cost summary for plan phase
        if cost_tracker.entries:
            cost_tracker.print_total_summary()

        print(f"\n{'='*60}")
        print("Step 1 Complete: project-init-final.md Generated")
        print(f"{'='*60}")
        print(f"\n📄 Review the generated file: {final_path}")
        print("\nThis file contains:")
        print("  - Your project requirements")
        print("  - Auto-generated testing strategy")
        if pipeline.codebase_analyses:
            print("  - Detected codebase patterns")
        print("\nNext steps:")
        print(f"  1. Review and edit project-init-final.md if needed")
        print(f"  2. Run: python main.py feature {final_path}")
        print(f"{'='*60}\n")

        return 0
    except Exception as e:
        print(f"Error during planning: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def run_feature(args: argparse.Namespace) -> int:
    """Run the feature generation phase - generates feature_list.json."""
    from src.pipeline.planning import PlanningPipeline
    from src.services.cost_tracker import CostTracker

    # Validate inputs
    project_init_final_path = Path(args.project_init_final)
    if not project_init_final_path.exists():
        print(f"Error: File not found: {args.project_init_final}")
        return 1

    # Check if it's project-init-final.md
    if "final" not in project_init_final_path.name.lower():
        print(f"Warning: Expected 'project-init-final.md', got '{project_init_final_path.name}'")
        print("Make sure you've run 'python main.py plan project-init.md' first.")

    # Create cost tracker for this phase
    cost_tracker = CostTracker()

    # Create pipeline
    pipeline = PlanningPipeline(
        project_init_path=str(project_init_final_path),
        output_dir=args.output,
        cost_tracker=cost_tracker,
    )

    try:
        # Run feature generation phase
        feature_list, saved_path = await pipeline.run_feature_phase(
            output_path=args.feature_list_output,
        )

        # Print cost summary for feature phase
        if cost_tracker.entries:
            cost_tracker.print_total_summary()

        print(f"\n{'='*60}")
        print("Step 2 Complete: Feature List Generated")
        print(f"{'='*60}")
        print(f"Project: {feature_list.project_name}")
        print(f"Features: {len(feature_list.features)}")

        if feature_list.branch_name:
            print(f"Branch: {feature_list.branch_name}")

        print("\nFeatures to implement:")
        for i, feat in enumerate(feature_list.features, 1):
            deps = f" (depends on: {', '.join(feat.depends_on)})" if feat.depends_on else ""
            print(f"  {i}. {feat.id}: {feat.name}{deps}")

        print(f"\n📄 Feature list saved to: {saved_path}")
        print("\nNext steps:")
        print(f"  1. Review {saved_path}")
        print(f"  2. Run: python main.py develop {saved_path}")
        print(f"{'='*60}\n")

        return 0
    except Exception as e:
        print(f"Error during feature generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def run_develop(args: argparse.Namespace) -> int:
    """Run the development phase."""
    from src.pipeline.development import DevelopmentPipeline

    # Validate inputs
    feature_list_path = Path(args.feature_list)
    if not feature_list_path.exists():
        print(f"Error: File not found: {args.feature_list}")
        return 1

    # Create pipeline with options
    pipeline = DevelopmentPipeline(
        feature_list_path=str(feature_list_path),
        resume=args.resume,
        feature_id=args.feature,
        comprehensive_testing=getattr(args, 'comprehensive_testing', False),
        create_smart_prs=getattr(args, 'create_smart_prs', False),
    )

    try:
        # Run development
        exit_reason = await pipeline.run()

        if exit_reason == "completed":
            print("\n✓ Development completed successfully!")
            return 0
        elif exit_reason == "interrupted":
            print("\nDevelopment interrupted. Use --resume to continue.")
            return 0
        elif exit_reason == "error":
            print("\n✗ Development encountered an error.")
            return 1
        else:
            print(f"\nDevelopment ended: {exit_reason}")
            return 0
    except Exception as e:
        print(f"Error during development: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_status(args: argparse.Namespace) -> int:
    """Show development status."""
    from src.pipeline.development import DevelopmentPipeline

    # Validate inputs
    feature_list_path = Path(args.feature_list)
    if not feature_list_path.exists():
        print(f"Error: File not found: {args.feature_list}")
        return 1

    # Create pipeline and get status
    pipeline = DevelopmentPipeline(
        feature_list_path=str(feature_list_path),
    )

    try:
        status = pipeline.get_status()

        print(f"\n{'='*50}")
        print("Development Status")
        print(f"{'='*50}")
        print(f"Status: {status['status']}")
        print(f"Features: {status['features_completed']}/{status['features_total']} completed")

        if status.get('features_in_progress'):
            print(f"In Progress: {status['features_in_progress']}")

        if status.get('session_count'):
            print(f"Sessions: {status['session_count']}")

        if status.get('branch'):
            print(f"Branch: {status['branch']}")

        # Show cost data if available
        state_manager = pipeline.setup_state_manager()
        state = state_manager.load()
        if state and state.cost_tracking and state.cost_tracking.total_cost > 0:
            ct = state.cost_tracking
            print(f"\n💰 Cost Summary:")
            print(f"   Total: ${ct.total_cost:.4f}")
            print(f"   Tokens: {ct.total_input_tokens:,} in / {ct.total_output_tokens:,} out")
            for phase, cost in sorted(ct.phase_costs.items()):
                print(f"   {phase.capitalize()}: ${cost:.4f}")

        print(f"{'='*50}\n")
        return 0
    except Exception as e:
        print(f"Error getting status: {e}")
        return 1


def run_confidence_report(args: argparse.Namespace) -> int:
    """Generate comprehensive confidence report."""
    import json
    from pathlib import Path
    from src.models.testing import ComprehensiveTestReport
    from src.models.pull_request import SmartPRPlan
    from src.pipeline.development import DevelopmentPipeline

    # Validate inputs
    feature_list_path = Path(args.feature_list)
    if not feature_list_path.exists():
        print(f"Error: File not found: {args.feature_list}")
        return 1

    # Create pipeline to access working directory
    pipeline = DevelopmentPipeline(
        feature_list_path=str(feature_list_path),
    )

    try:
        pipeline.load_feature_list()
        working_dir = Path(pipeline.get_working_directory())

        # Load state if available
        state_manager = pipeline.setup_state_manager()
        state = state_manager.load()

        if not state:
            print("No development state found. Run 'develop' command first.")
            return 1

        # Load test report if available
        test_report = None
        if state.comprehensive_test_report and Path(state.comprehensive_test_report).exists():
            try:
                with open(state.comprehensive_test_report, 'r') as f:
                    test_data = json.load(f)
                    test_report = ComprehensiveTestReport(**test_data)
            except Exception as e:
                print(f"Warning: Could not load test report: {e}")

        # Load PR plan if available
        pr_plan = None
        if state.smart_pr_plan and Path(state.smart_pr_plan).exists():
            try:
                with open(state.smart_pr_plan, 'r') as f:
                    pr_data = json.load(f)
                    pr_plan = SmartPRPlan(**pr_data)
            except Exception as e:
                print(f"Warning: Could not load PR plan: {e}")

        # Generate comprehensive confidence report
        _generate_detailed_confidence_report(
            pipeline.feature_list,
            state,
            test_report,
            pr_plan,
            working_dir
        )

        return 0

    except Exception as e:
        print(f"Error generating confidence report: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _generate_detailed_confidence_report(feature_list, state, test_report, pr_plan, working_dir):
    """Generate detailed confidence report."""
    print("╔" + "="*78 + "╗")
    print("║" + " COMPREHENSIVE CONFIDENCE REPORT ".center(78) + "║")
    print("╚" + "="*78 + "╝")

    # Project overview
    print(f"\n📋 PROJECT: {feature_list.project_name}")
    print(f"📁 DIRECTORY: {working_dir}")
    print(f"📅 GENERATED: {state.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    # Feature completion summary
    completed_features = len(state.get_completed_feature_ids())
    total_features = len(feature_list.features)
    completion_rate = (completed_features / total_features) * 100 if total_features > 0 else 0

    print(f"\n🎯 DEVELOPMENT SUMMARY:")
    print(f"   ✅ Features Completed: {completed_features}/{total_features} ({completion_rate:.1f}%)")
    print(f"   🔄 Development Sessions: {state.context_tracking.session_count}")
    print(f"   🌿 Branch: {state.branch_name or 'N/A'}")

    # Testing summary
    if test_report:
        print(f"\n🧪 COMPREHENSIVE TESTING RESULTS:")
        print(f"   📊 Total Tests: {test_report.total_tests}")
        print(f"   ✅ Tests Passed: {test_report.total_passed}")
        print(f"   ❌ Tests Failed: {test_report.total_tests - test_report.total_passed}")
        print(f"   📈 Success Rate: {(test_report.total_passed/test_report.total_tests)*100:.1f}%")

        print(f"\n   📋 Test Suite Breakdown:")
        print(f"      • Individual Feature Tests: {len(test_report.individual_tests)} suites")
        if test_report.integration_tests:
            print(f"      • Integration Tests: {test_report.integration_tests.total_tests} tests")
        if test_report.e2e_tests:
            print(f"      • End-to-End Tests: {test_report.e2e_tests.total_tests} tests")
        if test_report.stress_tests:
            print(f"      • Stress Tests: {test_report.stress_tests.total_tests} tests")
        if test_report.failure_tests:
            print(f"      • Failure Tests: {test_report.failure_tests.total_tests} tests")

        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        confidence_color = confidence_emoji.get(test_report.confidence_level, "🟡")
        print(f"\n   {confidence_color} TESTING CONFIDENCE: {test_report.confidence_level.upper()}")
    else:
        print(f"\n🧪 COMPREHENSIVE TESTING: Not run (use --comprehensive-testing flag)")

    # PR summary
    if pr_plan:
        print(f"\n📋 SMART PULL REQUESTS:")
        print(f"   📊 PRs Created: {len(pr_plan.pr_groups)}")
        print(f"   ⏱️  Total Review Time: ~{pr_plan.total_estimated_review_time} minutes")
        print(f"   📏 Average PR Size: {pr_plan.average_pr_size:.1f} features per PR")

        print(f"\n   📝 Pull Request Details:")
        for i, pr_group in enumerate(pr_plan.pr_groups, 1):
            deps = f" (depends on: {', '.join(pr_group.dependencies)})" if pr_group.dependencies else ""
            print(f"      {i}. {pr_group.name}: {len(pr_group.features)} features, ~{pr_group.estimated_review_time}min{deps}")

        if state.created_prs:
            print(f"\n   🔗 Pull Request URLs:")
            for i, pr_url in enumerate(state.created_prs, 1):
                print(f"      {i}. {pr_url}")
    else:
        print(f"\n📋 SMART PULL REQUESTS: Not created (use --create-smart-prs flag)")

    # Overall confidence assessment
    print(f"\n🎯 OVERALL CONFIDENCE ASSESSMENT:")

    if test_report and test_report.all_tests_pass and test_report.confidence_level == "high":
        confidence = "🟢 HIGH CONFIDENCE - PRODUCTION READY"
        recommendation = "✅ Code is thoroughly tested and ready for production deployment"
    elif test_report and test_report.all_tests_pass:
        confidence = "🟡 MEDIUM CONFIDENCE - REVIEW RECOMMENDED"
        recommendation = "⚠️  Code passes all tests but may benefit from additional review"
    elif completed_features == total_features:
        confidence = "🟡 MEDIUM CONFIDENCE - TESTING RECOMMENDED"
        recommendation = "⚠️  All features completed but comprehensive testing not performed"
    else:
        confidence = "🔴 LOW CONFIDENCE - DEVELOPMENT INCOMPLETE"
        recommendation = "❌ Development is not complete or tests are failing"

    print(f"   {confidence}")
    print(f"   {recommendation}")

    # Cost summary
    if state.cost_tracking and state.cost_tracking.total_cost > 0:
        ct = state.cost_tracking
        print(f"\n💰 API COST SUMMARY:")
        print(f"   Total Tokens: {ct.total_input_tokens:,} in / {ct.total_output_tokens:,} out")
        print(f"   Total Cost: ${ct.total_cost:.4f}")
        if ct.phase_costs:
            print(f"\n   Phase Breakdown:")
            for phase, cost in sorted(ct.phase_costs.items()):
                print(f"      {phase.capitalize()}: ${cost:.4f}")
        if ct.feature_costs:
            print(f"\n   Per-Feature Breakdown:")
            for feat_id, cost in sorted(ct.feature_costs.items()):
                print(f"      {feat_id}: ${cost:.4f}")
    else:
        print(f"\n💰 API COST: No cost data available")

    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if not test_report:
        print("   • Run development with --comprehensive-testing for full test coverage")
    if not pr_plan:
        print("   • Run development with --create-smart-prs for organized code review")
    if completed_features < total_features:
        print(f"   • Complete remaining {total_features - completed_features} features")
    if test_report and not test_report.all_tests_pass:
        print("   • Fix failing tests before proceeding to production")

    print(f"\n" + "="*80)


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "plan":
        return asyncio.run(run_plan(args))
    elif args.command == "feature":
        return asyncio.run(run_feature(args))
    elif args.command == "develop":
        return asyncio.run(run_develop(args))
    elif args.command == "status":
        return run_status(args)
    elif args.command == "confidence-report":
        return run_confidence_report(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
