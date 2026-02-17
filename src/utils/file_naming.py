"""File naming utilities for consistent project file naming."""

from pathlib import Path
import re


def extract_base_name(file_path: str) -> str:
    """
    Extract base name from user-provided project init file.

    Args:
        file_path: Path to user's project init file

    Returns:
        Base name for generating other files

    Examples:
        extract_base_name("calculator-subtract-project-init.md")
        -> "calculator-subtract"

        extract_base_name("/path/to/my-app-init.md")
        -> "my-app"

        extract_base_name("project-init.md")
        -> "project"
    """
    file_path = Path(file_path)
    # Remove .md extension if present
    stem = file_path.stem

    # Remove common suffixes that indicate it's an init file
    patterns_to_remove = [
        r'-project-init$',
        r'-init$',
        r'_project_init$',
        r'_init$'
    ]

    base_name = stem
    for pattern in patterns_to_remove:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)

    # If nothing was removed and we still have common init patterns, extract project name
    if base_name == stem:
        if 'project-init' in stem.lower():
            # Extract everything before 'project-init'
            base_name = re.sub(r'-?project-init.*$', '', stem, flags=re.IGNORECASE)
        elif stem.lower().endswith('init'):
            # Extract everything before 'init'
            base_name = re.sub(r'-?init$', '', stem, flags=re.IGNORECASE)

    # Clean up any trailing dashes or underscores
    base_name = base_name.strip('-_')

    # If we end up with empty string, use the original stem
    return base_name if base_name else stem


def generate_refined_filename(original_file_path: str) -> str:
    """Generate filename for refined project specification."""
    base_name = extract_base_name(original_file_path)
    return f"{base_name}-refined.md"


def generate_features_filename(original_file_path: str) -> str:
    """Generate filename for feature list JSON."""
    base_name = extract_base_name(original_file_path)
    return f"{base_name}-features.json"


def generate_analysis_filename(original_file_path: str) -> str:
    """Generate filename for codebase analysis cache JSON."""
    base_name = extract_base_name(original_file_path)
    return f"{base_name}-codebase-analysis.json"


def generate_report_filename(original_file_path: str, report_type: str) -> str:
    """Generate filename for various reports."""
    base_name = extract_base_name(original_file_path)
    return f"{base_name}-{report_type}.json"