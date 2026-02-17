"""Smart Pull Request management service for grouping features into reviewable PRs."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.feature import Repository
from collections import defaultdict

from ..models.feature import Feature, FeatureList
from ..models.pull_request import PRGroup, SmartPRPlan, PRCreationResult
from ..services.git_manager import GitManager
from ..services.branch_manager import BranchManager
from ..services.github_repo_initializer import GitHubRepoInitializer


class SmartPRManager:
    """Service for intelligently grouping features into Pull Requests."""

    def __init__(self, working_directory: str, git_manager: GitManager, branch_manager: BranchManager):
        """Initialize the Smart PR Manager.

        Args:
            working_directory: Path to the project directory (for single repo) or base directory (for multi-repo)
            git_manager: Git operations manager
            branch_manager: Branch management service
        """
        self.working_dir = Path(working_directory)
        self.git_manager = git_manager
        self.branch_manager = branch_manager
        self.github_initializer = GitHubRepoInitializer(working_directory)
        self.repo_github_initializers = {}  # Cache for multi-repo initializers

    def _is_multi_repo_project(self, feature_list: FeatureList) -> bool:
        """Check if this is a multi-repository project."""
        return feature_list.project_type == "multi_repo" and len(feature_list.repositories) > 1

    def _get_affected_repositories(self, features: List[Feature], feature_list: FeatureList) -> Dict[str, List[Feature]]:
        """Group features by affected repositories."""
        repo_features = defaultdict(list)

        for feature in features:
            if feature.repo_tasks:
                # Multi-repo feature - group by repository
                affected_repos = set(task.repo_id for task in feature.repo_tasks)
                for repo_id in affected_repos:
                    repo_features[repo_id].append(feature)
            else:
                # Single repo feature or legacy format
                if feature_list.repositories:
                    # Default to first repository if no specific repo tasks
                    repo_features[feature_list.repositories[0].id].append(feature)
                else:
                    # New project or single repo - use default key
                    repo_features["default"].append(feature)

        return dict(repo_features)

    def create_smart_pr_plan(self, completed_features: List[Feature], feature_list: FeatureList, base_name: Optional[str] = None) -> SmartPRPlan:
        """Group features into logical, reviewable Pull Requests.

        Args:
            completed_features: List of completed features
            feature_list: Complete feature list with project info
            base_name: Base name for plan file naming (optional)

        Returns:
            Smart PR plan with grouped features
        """
        print("📋 Creating Smart PR plan...")

        if self._is_multi_repo_project(feature_list):
            print("🔗 Multi-repository project detected")
            return self._create_multi_repo_pr_plan(completed_features, feature_list, base_name)
        else:
            print("📁 Single repository project")
            return self._create_single_repo_pr_plan(completed_features, feature_list, base_name)

    def _create_single_repo_pr_plan(self, completed_features: List[Feature], feature_list: FeatureList, base_name: Optional[str] = None) -> SmartPRPlan:
        """Create PR plan for single repository projects."""
        # Analyze feature dependencies
        dependencies = self._analyze_feature_dependencies(completed_features)

        # Group features by functionality and size
        pr_groups = self._group_features_intelligently(completed_features, feature_list, dependencies)

        # Calculate review order based on dependencies
        review_order = self._calculate_review_order(pr_groups, dependencies)

        # Calculate total estimated review time
        total_review_time = sum(pr.estimated_review_time for pr in pr_groups)

        plan = SmartPRPlan(
            project_name=feature_list.project_name,
            total_features=len(completed_features),
            pr_groups=pr_groups,
            review_order=review_order,
            total_estimated_review_time=total_review_time,
            dependency_map=self._create_dependency_map(pr_groups)
        )

        # Save plan to file with custom naming
        if base_name:
            plan_filename = f"{base_name}-smart-pr-plan.json"
        else:
            plan_filename = "smart_pr_plan.json"

        plan_path = self.working_dir / plan_filename
        with open(plan_path, 'w') as f:
            json.dump(plan.model_dump(), f, indent=2, default=str)

        print(f"✅ Smart PR plan saved to {plan_path}")
        return plan

    def _create_multi_repo_pr_plan(self, completed_features: List[Feature], feature_list: FeatureList, base_name: Optional[str] = None) -> SmartPRPlan:
        """Create PR plan for multi-repository projects."""
        # Group features by affected repositories
        repo_features = self._get_affected_repositories(completed_features, feature_list)

        all_pr_groups = []
        group_id_counter = 1

        print(f"📊 Features span {len(repo_features)} repositories:")
        for repo_id, features in repo_features.items():
            repo = feature_list.get_repository(repo_id)
            repo_name = repo.id if repo else repo_id
            print(f"   • {repo_name}: {len(features)} features")

            # Create PR groups for this repository
            dependencies = self._analyze_feature_dependencies(features)
            repo_pr_groups = self._group_features_intelligently(features, feature_list, dependencies, repo_id)

            # Update PR group IDs to be globally unique and add repository context
            for pr_group in repo_pr_groups:
                pr_group.id = f"PR-{group_id_counter:02d}"
                pr_group.repository_id = repo_id
                pr_group.name = f"[{repo_name}] {pr_group.name}"
                group_id_counter += 1

            all_pr_groups.extend(repo_pr_groups)

        # Calculate cross-repository dependencies
        self._set_cross_repo_pr_dependencies(all_pr_groups, completed_features, feature_list)

        # Calculate review order based on cross-repo dependencies
        review_order = self._calculate_review_order(all_pr_groups, {})

        # Calculate total estimated review time
        total_review_time = sum(pr.estimated_review_time for pr in all_pr_groups)

        plan = SmartPRPlan(
            project_name=feature_list.project_name,
            total_features=len(completed_features),
            pr_groups=all_pr_groups,
            review_order=review_order,
            total_estimated_review_time=total_review_time,
            dependency_map=self._create_dependency_map(all_pr_groups)
        )

        # Save plan to file with custom naming
        if base_name:
            plan_filename = f"{base_name}-smart-pr-plan.json"
        else:
            plan_filename = "smart_pr_plan.json"

        plan_path = self.working_dir / plan_filename
        with open(plan_path, 'w') as f:
            json.dump(plan.model_dump(), f, indent=2, default=str)

        print(f"✅ Multi-repo Smart PR plan saved to {plan_path}")
        return plan

    async def create_pull_requests(self, pr_plan: SmartPRPlan, feature_list: FeatureList) -> PRCreationResult:
        """Create actual GitHub PRs from the plan.

        Args:
            pr_plan: Smart PR plan to execute
            feature_list: Feature list with project information

        Returns:
            Result of PR creation with success/failure info
        """
        print("🚀 Creating Pull Requests...")

        if self._is_multi_repo_project(feature_list):
            print("🔗 Creating PRs for multi-repository project")
            return await self._create_multi_repo_prs(pr_plan, feature_list)
        else:
            print("📁 Creating PRs for single repository project")
            return await self._create_single_repo_prs(pr_plan, feature_list)

    async def _create_single_repo_prs(self, pr_plan: SmartPRPlan, feature_list: FeatureList) -> PRCreationResult:
        """Create PRs for single repository projects."""
        created_prs = []
        failed_prs = []

        for pr_group in pr_plan.pr_groups:
            try:
                # Create branch for this PR group
                branch_name = f"feature/{pr_group.id.lower().replace(' ', '-')}"
                pr_group.branch_name = branch_name

                # Create and checkout new branch
                await self._create_pr_branch(pr_group, branch_name)

                # Cherry-pick commits for features in this group
                await self._collect_feature_commits(pr_group)

                # Push branch to remote
                await self._push_pr_branch(pr_group)

                # Create GitHub PR with auto-generated description
                pr_url = await self._create_github_pr(pr_group)
                pr_group.pr_url = pr_url
                created_prs.append(pr_url)

                print(f"✅ Created PR: {pr_group.name} -> {pr_url}")

            except Exception as e:
                print(f"❌ Failed to create PR for {pr_group.name}: {e}")
                print(f"    Make sure you have a GitHub repository set up with 'git remote add origin <repo-url>'")
                failed_prs.append(pr_group.id)

        return PRCreationResult(
            plan=pr_plan,
            created_prs=created_prs,
            failed_prs=failed_prs,
            creation_timestamp=datetime.now().isoformat()
        )

    async def _create_multi_repo_prs(self, pr_plan: SmartPRPlan, feature_list: FeatureList) -> PRCreationResult:
        """Create PRs for multi-repository projects."""
        created_prs = []
        failed_prs = []

        for pr_group in pr_plan.pr_groups:
            try:
                # Get repository information
                repo_id = getattr(pr_group, 'repository_id', None)
                if not repo_id:
                    print(f"⚠️ No repository ID found for PR group {pr_group.id}, skipping")
                    failed_prs.append(pr_group.id)
                    continue

                repository = feature_list.get_repository(repo_id)
                if not repository:
                    print(f"⚠️ Repository {repo_id} not found for PR group {pr_group.id}, skipping")
                    failed_prs.append(pr_group.id)
                    continue

                # Create branch for this PR group in the correct repository
                branch_name = f"feature/{pr_group.id.lower().replace(' ', '-')}"
                pr_group.branch_name = branch_name

                # Create and checkout new branch in the specific repository
                await self._create_pr_branch_multi_repo(pr_group, branch_name, repository)

                # Cherry-pick commits for features in this group
                await self._collect_feature_commits_multi_repo(pr_group, repository)

                # Push branch to remote
                await self._push_pr_branch_multi_repo(pr_group, repository)

                # Create GitHub PR with auto-generated description
                pr_url = await self._create_github_pr_multi_repo(pr_group, repository)
                pr_group.pr_url = pr_url
                created_prs.append(pr_url)

                print(f"✅ Created PR in {repository.id}: {pr_group.name} -> {pr_url}")

            except Exception as e:
                print(f"❌ Failed to create PR for {pr_group.name}: {e}")
                print(f"    Make sure repository {repo_id} has a GitHub remote set up")
                failed_prs.append(pr_group.id)

        return PRCreationResult(
            plan=pr_plan,
            created_prs=created_prs,
            failed_prs=failed_prs,
            creation_timestamp=datetime.now().isoformat()
        )

    def _analyze_feature_dependencies(self, features: List[Feature]) -> Dict[str, List[str]]:
        """Analyze dependencies between features."""
        dependencies = {}
        for feature in features:
            dependencies[feature.id] = feature.depends_on.copy()
        return dependencies

    def _group_features_intelligently(
        self,
        features: List[Feature],
        feature_list: FeatureList,
        dependencies: Dict[str, List[str]],
        repository_id: Optional[str] = None
    ) -> List[PRGroup]:
        """Group features into logical PRs based on functionality and dependencies."""

        # Categorize features by type/functionality
        feature_categories = self._categorize_features(features)

        # Create PR groups
        pr_groups = []
        group_id_counter = 1

        # Group 1: Foundation features (database, auth, core setup)
        foundation_features = feature_categories.get('foundation', [])
        if foundation_features:
            pr_groups.append(self._create_pr_group(
                f"PR-{group_id_counter:02d}",
                "Foundation Setup",
                "Core infrastructure and setup",
                foundation_features
            ))
            group_id_counter += 1

        # Group 2-3: Business logic features (split if too large)
        business_features = feature_categories.get('business', [])
        if business_features:
            # Split into multiple PRs if too many features
            business_chunks = self._split_features_by_size(business_features, max_features=4)
            for i, chunk in enumerate(business_chunks):
                suffix = f" - Part {i + 1}" if len(business_chunks) > 1 else ""
                pr_groups.append(self._create_pr_group(
                    f"PR-{group_id_counter:02d}",
                    f"Core Business Logic{suffix}",
                    "Main application features and business logic",
                    chunk
                ))
                group_id_counter += 1

        # Group 4: API and integration features
        api_features = feature_categories.get('api', [])
        integration_features = feature_categories.get('integration', [])
        external_features = api_features + integration_features
        if external_features:
            pr_groups.append(self._create_pr_group(
                f"PR-{group_id_counter:02d}",
                "API Layer & Integration",
                "API endpoints and external integrations",
                external_features
            ))
            group_id_counter += 1

        # Group 5: Any remaining features
        remaining_features = feature_categories.get('other', [])
        if remaining_features:
            pr_groups.append(self._create_pr_group(
                f"PR-{group_id_counter:02d}",
                "Additional Features",
                "Additional functionality and improvements",
                remaining_features
            ))

        # Set dependencies between PR groups
        self._set_pr_dependencies(pr_groups, dependencies)

        # Update feature models with PR group assignments
        self._assign_features_to_pr_groups(features, pr_groups)

        return pr_groups

    def _categorize_features(self, features: List[Feature]) -> Dict[str, List[Feature]]:
        """Categorize features by type/functionality."""
        categories = defaultdict(list)

        for feature in features:
            feature_name = feature.name.lower()
            feature_desc = feature.description.lower()

            # Foundation features (database, auth, setup)
            if any(keyword in feature_name + feature_desc for keyword in [
                'database', 'schema', 'migration', 'auth', 'login', 'setup', 'config', 'init'
            ]):
                categories['foundation'].append(feature)

            # API features
            elif any(keyword in feature_name + feature_desc for keyword in [
                'api', 'endpoint', 'rest', 'graphql', 'route'
            ]):
                categories['api'].append(feature)

            # Integration features
            elif any(keyword in feature_name + feature_desc for keyword in [
                'integration', 'webhook', 'external', 'third-party', 'service'
            ]):
                categories['integration'].append(feature)

            # Business logic features
            else:
                categories['business'].append(feature)

        return dict(categories)

    def _split_features_by_size(self, features: List[Feature], max_features: int = 4) -> List[List[Feature]]:
        """Split features into chunks of reasonable size."""
        chunks = []
        for i in range(0, len(features), max_features):
            chunks.append(features[i:i + max_features])
        return chunks

    def _create_pr_group(self, group_id: str, name: str, description: str, features: List[Feature]) -> PRGroup:
        """Create a PR group from features."""
        feature_ids = [f.id for f in features]

        # Estimate metrics
        estimated_lines_added = len(features) * 50  # Rough estimate
        estimated_lines_deleted = len(features) * 10
        estimated_files_changed = len(features) * 3
        estimated_review_time = len(features) * 15  # 15 minutes per feature

        return PRGroup(
            id=group_id,
            name=name,
            description=description,
            features=feature_ids,
            estimated_review_time=estimated_review_time,
            files_changed=estimated_files_changed,
            lines_added=estimated_lines_added,
            lines_deleted=estimated_lines_deleted
        )

    def _set_pr_dependencies(self, pr_groups: List[PRGroup], feature_dependencies: Dict[str, List[str]]):
        """Set dependencies between PR groups based on feature dependencies."""
        # Create mapping of feature ID to PR group ID
        feature_to_pr = {}
        for pr_group in pr_groups:
            for feature_id in pr_group.features:
                feature_to_pr[feature_id] = pr_group.id

        # Set PR dependencies
        for pr_group in pr_groups:
            dependent_pr_groups = set()
            for feature_id in pr_group.features:
                # Check if this feature depends on features in other PR groups
                for dep_feature_id in feature_dependencies.get(feature_id, []):
                    if dep_feature_id in feature_to_pr:
                        dep_pr_group_id = feature_to_pr[dep_feature_id]
                        if dep_pr_group_id != pr_group.id:
                            dependent_pr_groups.add(dep_pr_group_id)

            pr_group.dependencies = list(dependent_pr_groups)

    def _set_cross_repo_pr_dependencies(self, pr_groups: List[PRGroup], completed_features: List[Feature], feature_list: FeatureList):
        """Set dependencies between PR groups across repositories."""
        # Create mapping of feature ID to PR group
        feature_to_pr_group = {}
        for pr_group in pr_groups:
            for feature_id in pr_group.features:
                feature_to_pr_group[feature_id] = pr_group

        # Check for cross-repository dependencies
        for pr_group in pr_groups:
            cross_repo_deps = set()

            for feature_id in pr_group.features:
                # Find the feature object
                feature = next((f for f in completed_features if f.id == feature_id), None)
                if not feature:
                    continue

                # Check each dependency
                for dep_feature_id in feature.depends_on:
                    if dep_feature_id in feature_to_pr_group:
                        dep_pr_group = feature_to_pr_group[dep_feature_id]

                        # Only add as dependency if it's a different PR group
                        if dep_pr_group.id != pr_group.id:
                            cross_repo_deps.add(dep_pr_group.id)

            # Update PR group dependencies (merge with existing ones)
            existing_deps = set(pr_group.dependencies) if pr_group.dependencies else set()
            pr_group.dependencies = list(existing_deps.union(cross_repo_deps))

    def _assign_features_to_pr_groups(self, features: List[Feature], pr_groups: List[PRGroup]):
        """Update feature models with their PR group assignments."""
        feature_to_pr = {}
        for pr_group in pr_groups:
            for feature_id in pr_group.features:
                feature_to_pr[feature_id] = pr_group.id

        for feature in features:
            if feature.id in feature_to_pr:
                feature.pr_group_id = feature_to_pr[feature.id]

    def _calculate_review_order(self, pr_groups: List[PRGroup], dependencies: Dict[str, List[str]]) -> List[str]:
        """Calculate the optimal order for reviewing PRs based on dependencies."""
        # Topological sort based on PR dependencies
        in_degree = {pr.id: len(pr.dependencies) for pr in pr_groups}
        queue = [pr.id for pr in pr_groups if len(pr.dependencies) == 0]
        order = []

        while queue:
            pr_id = queue.pop(0)
            order.append(pr_id)

            # Update in-degree for dependent PRs
            for pr in pr_groups:
                if pr_id in pr.dependencies:
                    in_degree[pr.id] -= 1
                    if in_degree[pr.id] == 0:
                        queue.append(pr.id)

        return order

    def _create_dependency_map(self, pr_groups: List[PRGroup]) -> Dict[str, List[str]]:
        """Create a dependency map for visualization."""
        return {pr.id: pr.dependencies for pr in pr_groups}

    async def _create_pr_branch_multi_repo(self, pr_group: PRGroup, branch_name: str, repository: 'Repository'):
        """Create a new branch for the PR group in a specific repository."""
        repo_path = Path(repository.path)

        # Switch to main branch first
        result = subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Try master if main doesn't exist
            subprocess.run(
                ["git", "checkout", "master"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

        # Create and checkout new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to create branch {branch_name} in {repository.id}: {result.stderr}")

    async def _collect_feature_commits_multi_repo(self, pr_group: PRGroup, repository: 'Repository'):
        """Collect and cherry-pick commits for features in this PR group from a specific repository."""
        # This would cherry-pick the specific commits for features in this PR
        # For now, we'll assume the commits are already in the current branch
        # In a real implementation, this would:
        # 1. Find commits associated with each feature in this repository
        # 2. Cherry-pick them onto the PR branch
        # 3. Handle conflicts if any
        pass

    async def _push_pr_branch_multi_repo(self, pr_group: PRGroup, repository: 'Repository'):
        """Push PR branch to remote repository."""
        if not pr_group.branch_name:
            raise Exception("Branch name not set for PR group")

        repo_path = Path(repository.path)
        result = subprocess.run(
            ["git", "push", "-u", "origin", pr_group.branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to push branch {pr_group.branch_name} in {repository.id}: {result.stderr}")

    async def _create_github_pr_multi_repo(self, pr_group: PRGroup, repository: 'Repository') -> str:
        """Create a GitHub Pull Request in a specific repository."""
        pr_title = pr_group.name
        pr_body = self._generate_pr_description_multi_repo(pr_group, repository)

        repo_path = Path(repository.path)

        # Use GitHub CLI to create PR
        result = subprocess.run([
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
            "--head", pr_group.branch_name,
            "--base", "main"
        ], cwd=repo_path, capture_output=True, text=True)

        if result.returncode != 0:
            # Try with master as base branch
            result = subprocess.run([
                "gh", "pr", "create",
                "--title", pr_title,
                "--body", pr_body,
                "--head", pr_group.branch_name,
                "--base", "master"
            ], cwd=repo_path, capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(f"Failed to create PR in {repository.id}: {result.stderr}")

        # Extract PR URL from output
        pr_url = result.stdout.strip()
        return pr_url

    def _generate_pr_description_multi_repo(self, pr_group: PRGroup, repository: 'Repository') -> str:
        """Generate comprehensive PR description for multi-repo projects."""
        return f"""## {pr_group.name}

{pr_group.description}

**Repository**: {repository.id} ({repository.language})

### Features Included:
{chr(10).join([f"- ✅ Feature {fid}" for fid in pr_group.features])}

### Review Metrics:
- **Estimated Review Time**: {pr_group.estimated_review_time} minutes
- **Files Changed**: ~{pr_group.files_changed} files
- **Lines Changed**: +{pr_group.lines_added} -{pr_group.lines_deleted}

### Dependencies:
{chr(10).join([f"- Requires {dep} to be merged first" for dep in pr_group.dependencies]) if pr_group.dependencies else "- No dependencies"}

### Multi-Repo Context:
This PR is part of a multi-repository project. Please coordinate with:
{chr(10).join([f"- {dep}" for dep in pr_group.dependencies]) if pr_group.dependencies else "- No cross-repository dependencies"}

### Review Focus Areas:
This PR introduces functionality in the **{repository.language}** repository that should be reviewed for:
- Code quality and maintainability
- Test coverage and quality
- Security considerations
- Performance implications
- Cross-repository API contracts

---
🤖 **Generated by Autonomous Coding Agent**
🔗 **Multi-Repository Project**
⏰ **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    async def _create_pr_branch(self, pr_group: PRGroup, branch_name: str):
        """Create a new branch for the PR group."""
        # Switch to main branch first
        await self.git_manager.checkout_branch("main")

        # Create and checkout new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to create branch {branch_name}: {result.stderr}")

    async def _collect_feature_commits(self, pr_group: PRGroup):
        """Collect and cherry-pick commits for features in this PR group."""
        # This would cherry-pick the specific commits for features in this PR
        # For now, we'll assume the commits are already in the current branch
        # In a real implementation, this would:
        # 1. Find commits associated with each feature
        # 2. Cherry-pick them onto the PR branch
        # 3. Handle conflicts if any
        pass

    async def _push_pr_branch(self, pr_group: PRGroup):
        """Push PR branch to remote repository."""
        if not pr_group.branch_name:
            raise Exception("Branch name not set for PR group")

        result = subprocess.run(
            ["git", "push", "-u", "origin", pr_group.branch_name],
            cwd=self.working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to push branch {pr_group.branch_name}: {result.stderr}")


    async def _create_github_pr(self, pr_group: PRGroup) -> str:
        """Create a GitHub Pull Request."""
        pr_title = pr_group.name
        pr_body = self._generate_pr_description(pr_group)

        # Use GitHub CLI to create PR
        result = subprocess.run([
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
            "--head", pr_group.branch_name,
            "--base", "main"
        ], cwd=self.working_dir, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Failed to create PR: {result.stderr}")

        # Extract PR URL from output
        pr_url = result.stdout.strip()
        return pr_url

    def _generate_pr_description(self, pr_group: PRGroup) -> str:
        """Generate comprehensive PR description."""
        return f"""## {pr_group.name}

{pr_group.description}

### Features Included:
{chr(10).join([f"- ✅ Feature {fid}" for fid in pr_group.features])}

### Review Metrics:
- **Estimated Review Time**: {pr_group.estimated_review_time} minutes
- **Files Changed**: ~{pr_group.files_changed} files
- **Lines Changed**: +{pr_group.lines_added} -{pr_group.lines_deleted}

### Dependencies:
{chr(10).join([f"- Requires {dep} to be merged first" for dep in pr_group.dependencies]) if pr_group.dependencies else "- No dependencies"}

### Review Focus Areas:
This PR introduces core functionality that should be reviewed for:
- Code quality and maintainability
- Test coverage and quality
- Security considerations
- Performance implications

---
🤖 **Generated by Autonomous Coding Agent**
⏰ **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""