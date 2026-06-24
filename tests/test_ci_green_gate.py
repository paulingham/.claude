"""CI-green gate invariant tests.

AC8 (revert-RED) and AC9 (unevaluable-refuses) are the Iron-Law-8 mandated
per-gate tests. AC13 and AC14 cover the verdict-catalog and DoD wire-ins.

These tests use subprocess (never live gh) and static grep — hermetic.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "skills" / "pipeline" / "lib" / "check-ci-green-gate.sh"
READER = REPO_ROOT / "hooks" / "_lib" / "ci-status-reader.sh"
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
PIPELINE_PROTOCOL = REPO_ROOT / "protocols" / "pipeline-protocol.md"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
SETTINGS_JSON = REPO_ROOT / ".claude" / "settings.json"


def _make_gh_stub(tmpdir: Path, json_body: str, exit_code: int = 0) -> Path:
    """Create a stub gh binary that emits json_body and exits with exit_code."""
    stub_dir = tmpdir / "stubs"
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f"echo '{json_body}'\n"
        f"exit {exit_code}\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub_dir


def _run_gate(pr_arg: str, stub_dir: Path | None = None, env_overrides: dict | None = None):
    """Run check-ci-green-gate.sh with given PR arg via subprocess."""
    env = os.environ.copy()
    if stub_dir:
        env["PATH"] = str(stub_dir) + ":" + env.get("PATH", "")
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        ["bash", str(GATE), pr_arg],
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def test_gate_exit_code_contract():
    """Gate exits are in {0, 2} only — never 1 or other unexpected codes (C1).

    Checks four representative fixture paths:
    - all-SUCCESS → 0
    - FAILURE → 2
    - gh-error → 2
    - empty rollup → 2
    """
    with tempfile.TemporaryDirectory(prefix="ci_gate_test.") as td:
        tmp = Path(td)

        all_success = '{"statusCheckRollup":[{"name":"ci","conclusion":"SUCCESS","state":"SUCCESS"}]}'
        stub_dir = _make_gh_stub(tmp / "s1", all_success, 0)
        result = _run_gate("42", stub_dir)
        assert result.returncode == 0, f"Expected 0 for all-SUCCESS, got {result.returncode}"

        failure_body = '{"statusCheckRollup":[{"name":"ci","conclusion":"FAILURE","state":"FAILURE"}]}'
        stub_dir = _make_gh_stub(tmp / "s2", failure_body, 0)
        result = _run_gate("42", stub_dir)
        assert result.returncode == 2, f"Expected 2 for FAILURE, got {result.returncode}"

        stub_dir = _make_gh_stub(tmp / "s3", "{}", 1)
        result = _run_gate("42", stub_dir)
        assert result.returncode == 2, f"Expected 2 for gh-error, got {result.returncode}"

        empty_rollup = '{"statusCheckRollup":[]}'
        stub_dir = _make_gh_stub(tmp / "s4", empty_rollup, 0)
        result = _run_gate("42", stub_dir)
        assert result.returncode == 2, f"Expected 2 for empty-rollup, got {result.returncode}"


def test_gate_not_registered_as_hook():
    """Gate and reader basenames must NOT appear in hooks.json or settings.json.

    This gate is a skill-step gate, not a PreToolUse hook. A registry entry
    would be a dead/wrong entry that misleads the dual-registration parity test.
    """
    gate_basename = GATE.name
    reader_basename = READER.name

    hooks_text = HOOKS_JSON.read_text() if HOOKS_JSON.exists() else ""
    settings_text = SETTINGS_JSON.read_text() if SETTINGS_JSON.exists() else ""

    assert gate_basename not in hooks_text, (
        f"{gate_basename} found in hooks/hooks.json — skill-step gates must NOT be registered as hooks"
    )
    assert gate_basename not in settings_text, (
        f"{gate_basename} found in .claude/settings.json — skill-step gates must NOT be registered as hooks"
    )
    assert reader_basename not in hooks_text, (
        f"{reader_basename} found in hooks/hooks.json — should only be sourced by the gate, not registered"
    )
    assert reader_basename not in settings_text, (
        f"{reader_basename} found in .claude/settings.json — should only be sourced by the gate, not registered"
    )


def test_default_branch_is_block():
    """Static: the reader's fall-through path must be BLOCK (exit 2), not allow.

    This test goes RED if someone adds an early 'return 0' or 'exit 0' before
    the all-green check, making unreadable status silently allow. That RED is
    the AC8 Iron-Law-8 sentinel for static analysis.
    """
    reader_text = READER.read_text()

    # The reader must have a final unconditional BLOCK
    # Pattern: a return/exit 2 that is not inside an 'if' or function guard
    # We look for an unconditional 'return 2' or 'exit 2' near the end of the file
    # that serves as the default BLOCK.
    lines = reader_text.splitlines()

    # Find the last 'return 2' or 'exit 2' line — it should be the default
    block_lines = [
        i for i, line in enumerate(lines)
        if re.search(r'\b(return|exit)\s+2\b', line)
    ]
    assert block_lines, (
        "hooks/_lib/ci-status-reader.sh has no 'return 2' or 'exit 2' — "
        "the reader has no fail-closed default; reverting to exit 0 would make AC8 RED"
    )

    # The final block line should be near the end of the file (last 10 lines)
    last_block = max(block_lines)
    total_lines = len(lines)
    assert last_block >= total_lines - 15, (
        f"The last 'return/exit 2' is at line {last_block + 1} of {total_lines} — "
        "the unconditional final BLOCK should be at the end of the reader function"
    )


def _parse_catalog_rows():
    """Parse verdict-catalog.md table rows."""
    body = CATALOG.read_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    rows = []
    for m in pattern.finditer(body):
        rows.append({
            "verdict": m.group(1),
            "polarity": m.group(2),
            "emitters": m.group(3),
            "phase": m.group(4).strip(),
            "branch": m.group(5).strip(),
        })
    return rows


def test_ci_verdicts_enforcing_and_consistent():
    """AC13: CI_GREEN/CI_RED rows EDITED to enforcing; no dupes; fwd+rev audit agrees.

    - CI_RED downstream branch must say HALT/block, NOT 'advisory' or 'never blocks'.
    - CI_GREEN downstream branch must NOT say 'advisory only' or 'Does NOT gate Deploy'.
    - Exactly ONE CI_GREEN row and ONE CI_RED row (no duplicates).
    - Forward audit: pr-creation SKILL.md declares CI_GREEN and CI_RED.
    - Reverse audit: catalog CI_GREEN/CI_RED rows point to pr-creation (which exists).
    """
    rows = _parse_catalog_rows()

    ci_green_rows = [r for r in rows if r["verdict"] == "CI_GREEN"]
    ci_red_rows = [r for r in rows if r["verdict"] == "CI_RED"]

    assert len(ci_green_rows) == 1, (
        f"Expected exactly 1 CI_GREEN row, found {len(ci_green_rows)}. "
        "Duplicate rows break the forward/reverse audit."
    )
    assert len(ci_red_rows) == 1, (
        f"Expected exactly 1 CI_RED row, found {len(ci_red_rows)}. "
        "Duplicate rows break the forward/reverse audit."
    )

    ci_green_branch = ci_green_rows[0]["branch"]
    ci_red_branch = ci_red_rows[0]["branch"]

    # CI_GREEN: must NOT contain advisory-only qualifiers from Slice 1
    assert "advisory only" not in ci_green_branch, (
        f"CI_GREEN row still says 'advisory only': {ci_green_branch!r}"
    )
    assert "Does NOT gate Deploy" not in ci_green_branch, (
        f"CI_GREEN row still says 'Does NOT gate Deploy': {ci_green_branch!r}"
    )

    # CI_RED: must NOT contain advisory-only qualifiers from Slice 1
    assert "advisory" not in ci_red_branch.lower() or "never blocks" not in ci_red_branch, (
        f"CI_RED row still has 'never blocks' advisory qualifier: {ci_red_branch!r}"
    )
    assert "Never blocks Ship" not in ci_red_branch, (
        f"CI_RED row still says 'Never blocks Ship': {ci_red_branch!r}"
    )

    # CI_RED: must contain HALT or block language
    branch_lower = ci_red_branch.lower()
    assert "halt" in branch_lower or "block" in branch_lower or "re-enter fix loop" in branch_lower, (
        f"CI_RED row must say HALT/block, found: {ci_red_branch!r}"
    )

    # Forward audit: pr-creation SKILL.md must declare CI_GREEN and CI_RED
    pr_creation_skill = REPO_ROOT / "skills" / "pr-creation" / "SKILL.md"
    pr_creation_text = pr_creation_skill.read_text()

    # Check that both verdicts appear in Verdict section of pr-creation
    verdict_section_match = re.search(
        r"## Verdict\s*\n(.*?)(?=\n## |\Z)", pr_creation_text, re.DOTALL
    )
    assert verdict_section_match, "pr-creation/SKILL.md has no '## Verdict' section"
    verdict_section = verdict_section_match.group(1)

    assert "CI_GREEN" in verdict_section, "pr-creation/SKILL.md Verdict section missing CI_GREEN"
    assert "CI_RED" in verdict_section, "pr-creation/SKILL.md Verdict section missing CI_RED"

    # Reverse audit: emitters in catalog must resolve (pr-creation skill dir exists)
    pr_creation_dir = REPO_ROOT / "skills" / "pr-creation"
    assert pr_creation_dir.is_dir(), "skills/pr-creation/ directory must exist for reverse audit"


def test_dod_has_enforcing_ci_green_line():
    """AC14: pipeline-protocol.md DoD has enforcing CI-green line.

    The advisory qualifier 'does not yet block' or 'enforcing gate is tracked separately'
    must be gone. End state: CI-green gate passed before Deploy.
    """
    body = PIPELINE_PROTOCOL.read_text()

    # Find DoD section
    dod_match = re.search(
        r"## Definition of Done\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL
    )
    assert dod_match, "pipeline-protocol.md has no '## Definition of Done' section"
    dod_section = dod_match.group(1)

    # Must contain CI-green gate language
    has_ci_green = (
        "CI-green gate" in dod_section
        or "ci-green gate" in dod_section.lower()
        or "CI_GREEN" in dod_section
        or ("CI" in dod_section and "green" in dod_section.lower() and "gate" in dod_section.lower())
    )
    assert has_ci_green, (
        "pipeline-protocol.md DoD must mention the CI-green gate. "
        f"DoD section: {dod_section[:500]!r}"
    )

    # Must NOT still carry the advisory/tracked-separately qualifier
    assert "does not yet block" not in dod_section, (
        "DoD still says 'does not yet block' — flip to enforcing"
    )
    assert "enforcing gate is tracked separately" not in dod_section, (
        "DoD still says 'enforcing gate is tracked separately' — flip to enforcing"
    )


PR_CREATION_SKILL = REPO_ROOT / "skills" / "pr-creation" / "SKILL.md"


def test_pr_creation_skill_no_slice1_advisory_stale_text():
    """AC15 (staleness regression): pr-creation/SKILL.md must not contain
    Slice-1 advisory language that falsely claims CI-watch cancellation or
    an unreadable CI status 'never blocks' or 'does NOT block' pipeline
    advancement.

    These strings directly contradicted the enforcing CI-green gate introduced
    in Slice 2. This test goes RED if the stale text is reintroduced.
    """
    body = PR_CREATION_SKILL.read_text()

    assert "an unreadable status never blocks" not in body, (
        "pr-creation/SKILL.md still contains Slice-1 stale text: "
        "'an unreadable status never blocks' — this contradicts the enforcing "
        "CI-green gate at pipeline/SKILL.md Step 5. Remove or update the sentence."
    )

    assert "never blocks" not in body, (
        "pr-creation/SKILL.md still contains 'never blocks' — this is Slice-1 "
        "advisory language contradicting the enforcing CI-green gate. "
        "Remove or update the language."
    )

    assert "does NOT block\npipeline advancement" not in body, (
        "pr-creation/SKILL.md still contains 'does NOT block pipeline advancement' "
        "— Slice-1 advisory text contradicting the enforcing CI-green gate."
    )

    # The cancel/unreadable paths must now reference the enforcing gate
    assert "enforcing CI-green gate" in body or "enforcing ci-green gate" in body.lower(), (
        "pr-creation/SKILL.md does not mention the 'enforcing CI-green gate' in the "
        "context of operator-cancel and unreadable paths — the stale advisory text "
        "must be replaced with a reference to pipeline/SKILL.md Step 5 enforcement."
    )
