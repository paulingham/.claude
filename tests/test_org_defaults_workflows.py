"""Tests for templates/org-defaults/.github/workflows/ YAML artifacts.

AC-B1d: repo-file-sync.yml is valid YAML with push trigger
AC-B1e: repository-created.yml is valid YAML with jobs + triggers, correct copy path, no injection
AC-B1f: required-workflow-drift-check.yml is valid YAML, multiline GITHUB_OUTPUT uses heredoc form
Security: all uses: directives are SHA-pinned (supply-chain)
"""
import re
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

ALL_WORKFLOW_FILES = [REPO_FILE_SYNC, REPO_CREATED, DRIFT_CHECK]

SHA_RE = re.compile(r"@[0-9a-f]{40}")


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
    """repository-created.yml parses as valid YAML with jobs and trigger blocks."""
    data = _load_yaml(REPO_CREATED)
    assert isinstance(data, dict), "repository-created.yml must be a valid YAML mapping"
    assert "jobs" in data, "repository-created.yml must have a 'jobs' block"
    # PyYAML parses bare 'on:' as boolean True key
    assert True in data, "repository-created.yml must have an 'on' trigger block"
    trigger = data[True]
    triggers = list(trigger.keys()) if isinstance(trigger, dict) else trigger
    assert any(
        t in ("repository_dispatch", "workflow_dispatch") for t in triggers
    ), "repository-created.yml must have repository_dispatch or workflow_dispatch trigger"


def test_repository_created_copy_source_path():
    """repository-created.yml copies settings.json from org-defaults root, not .claude/ subdir."""
    content = REPO_CREATED.read_text()
    assert "../org-defaults/.claude/settings.json" not in content, (
        "Wrong copy source: org-defaults repo has settings.json at ROOT after promotion, "
        "not under .claude/. Fix to ../org-defaults/settings.json"
    )
    assert "../org-defaults/settings.json" in content, (
        "repository-created.yml must copy from ../org-defaults/settings.json (root of org-defaults)"
    )


def test_repository_created_copy_failure_visible():
    """repository-created.yml cp for settings.json must not silently swallow errors."""
    content = REPO_CREATED.read_text()
    # Must not use 2>/dev/null || true pattern for the settings.json copy
    # (that pattern hides the failure — the workflow's primary purpose would silently no-op)
    lines = content.splitlines()
    for line in lines:
        if "settings.json" in line and "cp " in line:
            assert "2>/dev/null || true" not in line, (
                "settings.json copy must not silently suppress errors with '2>/dev/null || true'"
            )


def test_repository_created_no_expression_injection():
    """repository-created.yml must not interpolate github.event expressions directly in run: steps.

    Expressions like ${{ github.event.inputs.target_repo }} in run: blocks are
    script injection vectors (CWE-94). They must be passed via env: vars instead.
    Binding them in env: is correct and expected — only run: block injection is banned.
    """
    data = _load_yaml(REPO_CREATED)
    dangerous_expressions = [
        "${{ github.event.inputs.target_repo }}",
        "${{ github.event.client_payload.repository.full_name }}",
    ]
    # Walk all steps and check run: blocks only
    violations = []
    for job in data.get("jobs", {}).values():
        for step in job.get("steps", []):
            run_block = step.get("run", "")
            for expr in dangerous_expressions:
                if expr in run_block:
                    violations.append(
                        f"run: block in step {step.get('name', '?')!r} contains {expr!r}"
                    )
    assert not violations, (
        "github.event expressions must not be interpolated directly in run: blocks "
        "(CWE-94 script injection). Bind them to env: vars and reference via ${VAR} in shell.\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# AC-B1f: required-workflow-drift-check.yml
# ---------------------------------------------------------------------------

def test_drift_check_workflow_valid_yaml():
    """required-workflow-drift-check.yml parses as valid YAML."""
    data = _load_yaml(DRIFT_CHECK)
    assert isinstance(data, dict), "required-workflow-drift-check.yml must be a valid YAML mapping"


def test_drift_check_multiline_github_output_heredoc():
    """required-workflow-drift-check.yml must use heredoc form for multiline GITHUB_OUTPUT.

    echo -e "drift_report=${REPORT}" >> $GITHUB_OUTPUT truncates/corrupts multiline values.
    The heredoc form { echo "drift_report<<EOF"; ...; echo "EOF"; } >> $GITHUB_OUTPUT is correct.
    """
    content = DRIFT_CHECK.read_text()
    assert 'echo -e "drift_report=${REPORT}"' not in content and \
           "echo -e \"drift_report=${REPORT}\"" not in content, (
        "Must not use echo -e to set multiline GITHUB_OUTPUT value — use heredoc form instead"
    )
    assert "drift_report<<EOF" in content, (
        "Must use heredoc form: { echo \"drift_report<<EOF\"; ...; echo \"EOF\"; } >> \"$GITHUB_OUTPUT\""
    )


# ---------------------------------------------------------------------------
# Supply-chain: SHA-pinned actions (all 3 workflow files)
# ---------------------------------------------------------------------------

def test_all_workflow_uses_are_sha_pinned():
    """Every 'uses:' directive in all 3 workflow files must reference a full 40-char commit SHA.

    Mutable version tags (e.g. @v4, @v7) are a supply-chain risk for org-wide required workflows.
    Pin to full SHA: actions/checkout@<40hexchars> # v4.2.2
    """
    violations = []
    for wf_file in ALL_WORKFLOW_FILES:
        content = wf_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("uses:"):
                action_ref = stripped[len("uses:"):].strip()
                if not SHA_RE.search(action_ref):
                    violations.append(f"{wf_file.name}:{i}: {stripped}")
    assert not violations, (
        "All 'uses:' directives must be pinned to a full 40-char commit SHA. Violations:\n"
        + "\n".join(violations)
    )
