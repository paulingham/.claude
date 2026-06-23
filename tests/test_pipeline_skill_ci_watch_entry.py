"""Slice 1b — Verify advisory CI-watch entry note in skills/pipeline/SKILL.md.

AC10: skills/pipeline/SKILL.md Step 5 (Deploy) names the advisory CI-watch
      running after PR_CREATED and before the 'gh pr view --json state'
      merge-status check, with an explicit 'does NOT gate Deploy' note.

Goes RED before the entry note is added (Step 5 jumps straight to merge check),
GREEN after the note lands.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"


def _step5_section(text):
    """Extract Step 5 (Deploy) section text."""
    m = re.search(
        r"(### Step 5[:\s].+?)(?=\n### Step [0-9]|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(1) if m else None


def test_step5_names_advisory_ci_watch_before_merge_check():
    """AC10: pipeline SKILL.md Step 5 names advisory CI-watch after PR_CREATED,
    before merge-status check, with explicit 'does NOT gate Deploy' / advisory note."""
    text = SKILL.read_text()

    step5 = _step5_section(text)
    assert step5 is not None, (
        "skills/pipeline/SKILL.md must have a 'Step 5' (Deploy) section"
    )

    ci_watch_present = any(
        kw in step5
        for kw in ("CI-watch", "CI watch", "gh pr checks", "advisory CI", "5b")
    )
    assert ci_watch_present, (
        "skills/pipeline/SKILL.md Step 5 must name the advisory CI-watch "
        "running after PR_CREATED (e.g. 'advisory CI-watch', 'gh pr checks', "
        "or 'pr-creation Step 5b'). "
        "Currently Step 5 jumps straight to the merge-status check."
    )

    merge_check_present = any(
        kw in step5
        for kw in ("gh pr view", "json state", "merge status", "MERGED")
    )
    assert merge_check_present, (
        "Step 5 must still contain the merge-status check "
        "('gh pr view --json state' or equivalent). "
        "The CI-watch is an ENTRY NOTE before the existing check — "
        "the merge check itself must not be removed."
    )

    ci_watch_pos = -1
    for kw in ("CI-watch", "CI watch", "gh pr checks", "advisory CI", "5b"):
        pos = step5.find(kw)
        if pos != -1:
            ci_watch_pos = pos
            break

    merge_pos = -1
    for kw in ("gh pr view", "json state", "merge status"):
        pos = step5.find(kw)
        if pos != -1:
            merge_pos = pos
            break

    if ci_watch_pos != -1 and merge_pos != -1:
        assert ci_watch_pos < merge_pos, (
            f"CI-watch entry (pos {ci_watch_pos}) must appear BEFORE the "
            f"merge-status check (pos {merge_pos}) in Step 5."
        )

    not_gate_present = any(
        kw in step5
        for kw in (
            "does NOT gate", "does not gate", "NOT gate Deploy",
            "not gate Deploy", "advisory", "does not block Deploy",
            "Slice 2",
        )
    )
    assert not_gate_present, (
        "Step 5 CI-watch entry must include an explicit 'does NOT gate Deploy' "
        "or 'advisory' note — Slice 1 does NOT block the Deploy boundary on CI conclusion."
    )
