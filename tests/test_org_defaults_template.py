"""Tests for templates/org-defaults/ settings and managed-settings artifacts.

AC-B1a: settings.json is valid JSON, has enabledPlugins, no extraKnownMarketplaces, has cloud-bootstrap hook
AC-B1b: managed-settings.json has no secrets and uses local-directory install
AC-B1c: managed-settings.json PreToolUse permissionDecisionReason contains exact nudge strings
AC-B1g: README.md documents promotion path, Desktop gap, gh auth prerequisite
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates" / "org-defaults"
SETTINGS_FILE = TEMPLATES_DIR / "settings.json"
MANAGED_SETTINGS_FILE = TEMPLATES_DIR / "managed-settings.json"
README_FILE = TEMPLATES_DIR / "README.md"


# ---------------------------------------------------------------------------
# AC-B1a: settings.json
# ---------------------------------------------------------------------------

def test_settings_template_valid_json():
    """json.loads(open("templates/org-defaults/settings.json").read()) does not raise."""
    assert SETTINGS_FILE.exists(), "templates/org-defaults/settings.json must exist"
    data = json.loads(SETTINGS_FILE.read_text())
    assert isinstance(data, dict)


def test_settings_template_has_enabled_plugins():
    """enabledPlugins field == ["harness@adviser-group"] (exact list form for settings.json)."""
    data = json.loads(SETTINGS_FILE.read_text())
    assert "enabledPlugins" in data, "enabledPlugins must be present"
    enabled = data["enabledPlugins"]
    assert enabled == ["harness@adviser-group"], (
        f"settings.json enabledPlugins must be exactly [\"harness@adviser-group\"], got {enabled!r}"
    )


def test_settings_template_has_no_extra_known_marketplaces():
    """extraKnownMarketplaces key absent from settings template."""
    data = json.loads(SETTINGS_FILE.read_text())
    assert "extraKnownMarketplaces" not in data, (
        "extraKnownMarketplaces must NOT be present in the template "
        "(github source fails on private dot-named repo; cloud coverage via cloud-bootstrap.sh)"
    )


def test_settings_template_has_cloud_bootstrap_hook():
    """settings.json SessionStart hooks list contains a command referencing cloud-bootstrap.sh."""
    data = json.loads(SETTINGS_FILE.read_text())
    hooks = data.get("hooks", {})
    session_start = hooks.get("SessionStart", [])
    assert len(session_start) > 0, "SessionStart hooks must be present"
    # Collect all text from commands and args arrays
    all_hook_text = []
    for hook_group in session_start:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_hook_text.append(cmd)
            args = hook.get("args", [])
            all_hook_text.extend(str(a) for a in args)
    combined = " ".join(all_hook_text)
    assert "cloud-bootstrap.sh" in combined, (
        "At least one SessionStart hook command must reference cloud-bootstrap.sh"
    )


# ---------------------------------------------------------------------------
# AC-B1b: managed-settings.json
# ---------------------------------------------------------------------------

def test_managed_settings_has_no_secrets():
    """managed-settings.json contains no ghp_ or github_pat_ patterns."""
    assert MANAGED_SETTINGS_FILE.exists(), "templates/org-defaults/managed-settings.json must exist"
    content = MANAGED_SETTINGS_FILE.read_text()
    assert "ghp_" not in content, "managed-settings.json must not contain ghp_ token literals"
    assert "github_pat_" not in content, "managed-settings.json must not contain github_pat_ token literals"


def test_managed_settings_has_local_directory_install():
    """managed-settings.json SessionStart hook references local-directory install, not github shorthand."""
    content = MANAGED_SETTINGS_FILE.read_text()
    data = json.loads(content)
    hooks = data.get("hooks", {})
    session_start = hooks.get("SessionStart", [])
    assert len(session_start) > 0, "managed-settings.json must have SessionStart hooks"
    all_commands = []
    for hook_group in session_start:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_commands.append(cmd)
    combined = " ".join(all_commands)
    # Must reference the local marketplace directory path explicitly
    assert "local-marketplaces/adviser-group" in combined, (
        "SessionStart hook must reference local-marketplaces/adviser-group directory path"
    )
    # Confirm no bare 'github' source shorthand for marketplace add
    assert "marketplace add Adviser-Group" not in combined, (
        "Must not use github shorthand for marketplace add"
    )


# ---------------------------------------------------------------------------
# AC-B1c: nudge message exact strings
# ---------------------------------------------------------------------------

def test_nudge_message_contains_exact_strings():
    """managed-settings.json PreToolUse permissionDecisionReason contains exact nudge substrings."""
    content = MANAGED_SETTINGS_FILE.read_text()
    data = json.loads(content)
    hooks = data.get("hooks", {})
    pre_tool_use = hooks.get("PreToolUse", [])
    assert len(pre_tool_use) > 0, "managed-settings.json must have PreToolUse hooks"

    # Collect all commands from PreToolUse hooks
    all_commands = []
    for hook_group in pre_tool_use:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_commands.append(cmd)
    combined = " ".join(all_commands)

    required_substrings = [
        "Adviser harness not detected",
        "gh auth login",
        "ADVISER_HARNESS_OPT_OUT=1",
    ]
    for substring in required_substrings:
        assert substring in combined, (
            f"PreToolUse permissionDecisionReason must contain: {substring!r}"
        )


# ---------------------------------------------------------------------------
# AC-B1g: README.md
# ---------------------------------------------------------------------------

def test_settings_deny_list_is_superset_of_managed_settings_deny_list():
    """settings.json deny list must contain every rule present in managed-settings.json deny list."""
    settings_data = json.loads(SETTINGS_FILE.read_text())
    managed_data = json.loads(MANAGED_SETTINGS_FILE.read_text())
    settings_deny = set(settings_data.get("permissions", {}).get("deny", []))
    managed_deny = set(managed_data.get("permissions", {}).get("deny", []))
    missing = managed_deny - settings_deny
    assert not missing, (
        f"settings.json deny list is missing rules present in managed-settings.json:\n"
        + "\n".join(f"  {r!r}" for r in sorted(missing))
    )


def test_managed_settings_bootstrap_log_hygiene():
    """managed-settings.json bootstrap command must redirect git remote set-url to /dev/null."""
    data = json.loads(MANAGED_SETTINGS_FILE.read_text())
    hooks = data.get("hooks", {})
    session_start = hooks.get("SessionStart", [])
    all_commands = []
    for hook_group in session_start:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_commands.append(cmd)
    combined = " ".join(all_commands)
    # git remote set-url must be silenced so tokenized URL can't leak into the log
    assert "remote set-url origin" not in combined or (
        "remote set-url origin" in combined and ">/dev/null" in combined
    ), (
        "git remote set-url origin must redirect output to /dev/null "
        "to prevent tokenized URL leakage into harness-bootstrap.log"
    )


def test_managed_settings_bootstrap_log_perms():
    """managed-settings.json bootstrap subshell must use umask 077 or equivalent for log security."""
    data = json.loads(MANAGED_SETTINGS_FILE.read_text())
    hooks = data.get("hooks", {})
    session_start = hooks.get("SessionStart", [])
    all_commands = []
    for hook_group in session_start:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_commands.append(cmd)
    combined = " ".join(all_commands)
    assert "umask 077" in combined, (
        "Bootstrap subshell must set 'umask 077' before writing to harness-bootstrap.log "
        "so the log is created with 0600 permissions (no token URL leakage to other users)"
    )


def test_readme_documents_promotion_path():
    """README.md contains 'Adviser-Group/org-defaults'."""
    assert README_FILE.exists(), "templates/org-defaults/README.md must exist"
    content = README_FILE.read_text()
    assert "Adviser-Group/org-defaults" in content, (
        "README.md must document the promotion path to Adviser-Group/org-defaults"
    )


def test_readme_documents_desktop_gap():
    """README.md contains 'Desktop' and ('gap' or 'limitation' or 'not supported')."""
    content = README_FILE.read_text()
    assert "Desktop" in content, "README.md must mention Desktop"
    lower = content.lower()
    assert any(kw in lower for kw in ("gap", "limitation", "not supported")), (
        "README.md must document the Desktop gap/limitation"
    )


def test_readme_documents_gh_auth_prerequisite():
    """README.md contains 'gh auth login'."""
    content = README_FILE.read_text()
    assert "gh auth login" in content, (
        "README.md must document the gh auth login prerequisite"
    )


# ---------------------------------------------------------------------------
# Mandatory gap-fill (Verify probe 5 survivor): byte-for-byte sync check
# ---------------------------------------------------------------------------

def test_template_managed_settings_matches_repo_root_managed_settings():
    """templates/org-defaults/managed-settings.json must be byte-for-byte identical to
    the repo-root managed-settings.json.

    Both files are the canonical source of org-defaults; if they diverge the
    deployed template silently ships a stale policy.  The byte comparison catches
    any whitespace, comment, or content drift regardless of JSON semantic equivalence.
    """
    repo_root_file = REPO_ROOT / "managed-settings.json"
    assert repo_root_file.exists(), "repo-root managed-settings.json must exist"
    assert MANAGED_SETTINGS_FILE.exists(), (
        "templates/org-defaults/managed-settings.json must exist"
    )
    assert MANAGED_SETTINGS_FILE.read_bytes() == repo_root_file.read_bytes(), (
        "templates/org-defaults/managed-settings.json is out of sync with "
        "managed-settings.json at repo root.  Keep them byte-for-byte identical: "
        "edit one and copy to the other."
    )


# ---------------------------------------------------------------------------
# Candidate 1 gap-fill: tightened bootstrap log hygiene — redirect on set-url line
# ---------------------------------------------------------------------------

def test_managed_settings_bootstrap_set_url_redirect_is_adjacent():
    """managed-settings.json: git remote set-url origin must have >/dev/null 2>&1 immediately
    after the URL argument on the same logical command, not just somewhere in the blob.

    The existing test_managed_settings_bootstrap_log_hygiene passes if any >/dev/null
    exists anywhere in the command string.  This test uses a regex to assert the redirect
    is specifically on the remote set-url invocation so a future refactor cannot
    accidentally drop the per-command silencing while leaving another unrelated redirect.
    """
    data = json.loads(MANAGED_SETTINGS_FILE.read_text())
    hooks = data.get("hooks", {})
    session_start = hooks.get("SessionStart", [])
    all_commands = []
    for hook_group in session_start:
        for hook in hook_group.get("hooks", []):
            cmd = hook.get("command", "")
            all_commands.append(cmd)
    combined = " ".join(all_commands)

    # Match: remote set-url origin "<any token>" >/dev/null 2>&1
    # Allow for escaped quotes around the URL: \"$U\" or "$U" or $U
    pattern = re.compile(
        r'remote set-url origin\s+["\']?\S+["\']?\s+>/dev/null\s+2>&1'
    )
    assert pattern.search(combined), (
        "git remote set-url origin must be immediately followed by '>/dev/null 2>&1' "
        "on the same command (not just a >/dev/null somewhere else in the blob). "
        "This prevents the tokenized URL from leaking into harness-bootstrap.log."
    )
