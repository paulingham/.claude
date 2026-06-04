"""Tests for ROLLOUT.md structure additions from slice b2.

AC-B2a: ROLLOUT.md contains a section named "Server-managed settings console JSON" (or equivalent)
AC-B2b: ROLLOUT.md staged rollout section mentions "test cohort" or "staged"
AC-B2c: ROLLOUT.md cross-references templates/org-defaults/
AC-B2d: G1 scanner check (overlay-sync refs not added) — tested via bash scanner
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ROLLOUT_FILE = REPO_ROOT / "ROLLOUT.md"


def _content() -> str:
    assert ROLLOUT_FILE.exists(), "ROLLOUT.md must exist"
    return ROLLOUT_FILE.read_text()


# ---------------------------------------------------------------------------
# AC-B2a: Server-managed settings section
# ---------------------------------------------------------------------------

def test_rollout_has_server_managed_settings_section():
    """ROLLOUT.md contains 'Server-managed settings' or 'console JSON' heading."""
    content = _content()
    lower = content.lower()
    assert "server-managed settings" in lower or "console json" in lower, (
        "ROLLOUT.md must have a section about server-managed settings / console JSON"
    )


# ---------------------------------------------------------------------------
# AC-B2b: Staged rollout sequence
# ---------------------------------------------------------------------------

def test_rollout_staged_sequence_has_test_cohort():
    """ROLLOUT.md staged rollout section mentions 'test cohort' or 'staged'."""
    content = _content()
    lower = content.lower()
    assert "test cohort" in lower or "staged" in lower, (
        "ROLLOUT.md must describe a staged rollout sequence including a test cohort"
    )


# ---------------------------------------------------------------------------
# AC-B2c: Cross-reference to templates/org-defaults/
# ---------------------------------------------------------------------------

def test_rollout_references_templates_org_defaults():
    """ROLLOUT.md contains 'templates/org-defaults'."""
    content = _content()
    assert "templates/org-defaults" in content, (
        "ROLLOUT.md must cross-reference templates/org-defaults/"
    )
