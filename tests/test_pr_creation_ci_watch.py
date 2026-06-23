"""Slice 1b — Verify the CI-watch section exists in skills/pr-creation/SKILL.md.

AC4: A '### 5b.' CI-watch section exists between Step 5 and Step 6, naming
     'gh pr checks' and a poll-to-conclusion loop.
AC5: The CI-watch section names '--log-failed' AND fix loop language AND worktree.
AC5-bis: The arm step captures 'headRefOid' and per-poll SHA compare named.
AC6: The RED-path re-arm names 'git ls-remote' as the SHA verification step.
AC8: Step 6 preamble references CI-watch having run; CI-watch section precedes
     'pr_cost_annotate.py' in skill text (ordering proof).
AC11: The CI-watch section names an operator cancel/abort escape path emitting
      'watch-skipped:operator-cancel' with a not-a-block qualifier.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "pr-creation" / "SKILL.md"


def _skill_text():
    return SKILL.read_text()


def _step5b_section(text):
    """Extract the CI-watch section between Step 5 and Step 6."""
    m = re.search(
        r"(### 5b\..+?)(?=\n### 6\.|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(1) if m else None


def test_skill_has_ci_watch_section_between_steps_5_and_6():
    """AC4: CI-watch section exists between Step 5 and Step 6, names 'gh pr checks'."""
    text = _skill_text()

    step5_pos = text.find("### 5. Create Pull Request")
    assert step5_pos != -1, (
        "skills/pr-creation/SKILL.md must contain '### 5. Create Pull Request'"
    )

    step6_pos = text.find("### 6.")
    assert step6_pos != -1, (
        "skills/pr-creation/SKILL.md must contain a '### 6.' section"
    )

    step5b_pos = text.find("### 5b.")
    assert step5b_pos != -1, (
        "skills/pr-creation/SKILL.md must contain a '### 5b.' CI-watch section"
    )

    assert step5_pos < step5b_pos < step6_pos, (
        f"### 5b. must appear between ### 5. (pos {step5_pos}) and "
        f"### 6. (pos {step6_pos}), but found at pos {step5b_pos}"
    )

    section = _step5b_section(text)
    assert section is not None, "Could not extract ### 5b. section text"
    assert "gh pr checks" in section, (
        "CI-watch section must name 'gh pr checks' (the poll mechanism)"
    )


def test_red_path_names_log_failed_and_fix_loop():
    """AC5: CI-watch section names '--log-failed', fix loop language, and worktree."""
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found; AC4 failing"

    assert "--log-failed" in section, (
        "CI-watch section must name '--log-failed' for the RED path "
        "(pull failing CI logs)"
    )

    fix_loop_present = any(
        kw in section for kw in ("fix loop", "fix-engineer", "in-cycle fix", "fix engineer")
    )
    assert fix_loop_present, (
        "CI-watch section must name re-entering the in-cycle fix loop on RED "
        "(fix-engineer / fix loop language)"
    )

    assert "worktree" in section, (
        "CI-watch section must name 'worktree' to indicate the fix runs "
        "on the SAME build worktree (not a fresh one)"
    )


def test_poll_arm_captures_headrefoid():
    """AC5-bis: Arm step captures headRefOid; per-poll SHA compare named."""
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found; AC4 failing"

    assert "headRefOid" in section, (
        "CI-watch arm step must capture 'headRefOid' at arm time to guard "
        "against force-push producing a false-green against an unevaluated commit"
    )

    sha_compare_present = any(
        kw in section
        for kw in ("SHA", "sha", "check-run SHA", "matches", "compare")
    )
    assert sha_compare_present, (
        "CI-watch section must name per-poll SHA comparison against the captured "
        "headRefOid (e.g. 'compare check-run SHA to captured headRefOid')"
    )


def test_rearm_verifies_git_ls_remote_sha():
    """AC6: RED-path re-arm names 'git ls-remote' as the do-not-trust-self-report guard."""
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found; AC4 failing"

    assert "git ls-remote" in section, (
        "CI-watch re-arm step must name 'git ls-remote' to verify the fix-engineer's "
        "claimed SHA actually reached the remote before re-polling. "
        "See memory: ship-must-watch-remote-ci, fix-engineer-nested-worktree-side-branch."
    )


def test_cost_annotator_step_follows_ci_watch_in_skill_text():
    """AC8: CI-watch section precedes pr_cost_annotate.py; Step 6 preamble references CI-watch."""
    text = _skill_text()

    step5b_pos = text.find("### 5b.")
    assert step5b_pos != -1, "No ### 5b. CI-watch section found"

    annotate_pos = text.find("pr_cost_annotate.py")
    assert annotate_pos != -1, (
        "skills/pr-creation/SKILL.md must still reference 'pr_cost_annotate.py' "
        "(Step 6 cost annotator)"
    )

    assert step5b_pos < annotate_pos, (
        f"CI-watch (### 5b., pos {step5b_pos}) must appear before "
        f"pr_cost_annotate.py (pos {annotate_pos}) in skill text. "
        "The cost annotator (Step 6) must be reachable only after CI-watch."
    )

    step6_pos = text.find("### 6.")
    assert step6_pos != -1, "No ### 6. section found"

    step6_text = text[step6_pos: step6_pos + 400]
    ci_ref_present = any(
        kw in step6_text
        for kw in ("CI-watch", "CI watch", "5b", "checks pass", "checks confirmed")
    )
    assert ci_ref_present, (
        "Step 6 preamble must reference CI-watch having run "
        "(e.g. 'After the CI-watch confirms', '5b', etc.) "
        "to un-orphan the dangling forward-reference at pr-creation/SKILL.md:275."
    )


def test_ci_watch_names_operator_cancel_escape():
    """AC11: CI-watch section names an operator cancel escape with 'watch-skipped:operator-cancel'."""
    text = _skill_text()
    section = _step5b_section(text)
    assert section is not None, "No ### 5b. section found; AC4 failing"

    assert "watch-skipped:operator-cancel" in section, (
        "CI-watch section must name the operator cancel escape hatch emitting "
        "'watch-skipped:operator-cancel' (prevents operator being held hostage on "
        "a persistent-RED / flaky CI loop)"
    )

    not_a_block_present = any(
        kw in section
        for kw in (
            "not a block", "not blocking", "advisory", "unverified",
            "CI status unverified", "does not block",
        )
    )
    assert not_a_block_present, (
        "CI-watch operator cancel must include a 'not a block' / 'advisory' / "
        "'CI status unverified' qualifier — cancelling leaves CI status unverified "
        "but must NOT block pipeline advancement."
    )
