"""Tests for templates/org-defaults/.github/workflows/ YAML artifacts.

AC-B1d: repo-file-sync.yml is valid YAML with push trigger
AC-B1e: repository-created.yml is valid YAML
AC-B1f: required-workflow-drift-check.yml is valid YAML
"""
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / "templates" / "org-defaults" / ".github" / "workflows"
REPO_FILE_SYNC = WORKFLOWS_DIR / "repo-file-sync.yml"
REPO_CREATED = WORKFLOWS_DIR / "repository-created.yml"
DRIFT_CHECK = WORKFLOWS_DIR / "required-workflow-drift-check.yml"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, skipping if PyYAML not available."""
    if yaml is None:
        pytest.skip("PyYAML not installed — cannot parse YAML")
    assert path.exists(), f"{path} must exist"
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# AC-B1d: repo-file-sync.yml
# ---------------------------------------------------------------------------

def test_repo_file_sync_workflow_valid_yaml():
    """repo-file-sync.yml parses as valid YAML with push event."""
    data = _load_yaml(REPO_FILE_SYNC)
    assert isinstance(data, dict), "repo-file-sync.yml must be a valid YAML mapping"
    on_block = data.get("on", data.get(True, {}))  # 'on' is YAML keyword, may parse as True
    assert on_block is not None, "repo-file-sync.yml must have an 'on' trigger block"
    # Accept push trigger in various forms
    if isinstance(on_block, dict):
        assert "push" in on_block, "repo-file-sync.yml must have a 'push' trigger"
    elif isinstance(on_block, list):
        assert "push" in on_block, "repo-file-sync.yml must have a 'push' trigger"
    else:
        pytest.fail(f"Unexpected 'on' type: {type(on_block)}")


# ---------------------------------------------------------------------------
# AC-B1e: repository-created.yml
# ---------------------------------------------------------------------------

def test_repository_created_workflow_valid_yaml():
    """repository-created.yml parses as valid YAML."""
    data = _load_yaml(REPO_CREATED)
    assert isinstance(data, dict), "repository-created.yml must be a valid YAML mapping"
    assert "jobs" in data or "on" in data or True in data, (
        "repository-created.yml must have jobs or triggers"
    )


# ---------------------------------------------------------------------------
# AC-B1f: required-workflow-drift-check.yml
# ---------------------------------------------------------------------------

def test_drift_check_workflow_valid_yaml():
    """required-workflow-drift-check.yml parses as valid YAML."""
    data = _load_yaml(DRIFT_CHECK)
    assert isinstance(data, dict), "required-workflow-drift-check.yml must be a valid YAML mapping"
