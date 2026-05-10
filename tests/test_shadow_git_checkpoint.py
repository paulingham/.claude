"""Slice 1 + 3 + 4 + 5 — Python tests for shadow-git-checkpoint helpers and doc-surface contracts.

Test names encode the AC number per learning instinct
`instinct-ac-coverage-final-gate-gap`. The shell helpers are exercised via
``subprocess.run(['bash', '-c', ...])`` as the plan prescribes; doc-surface
ACs are exercised via ``grep``-style file reads.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
HELPERS = REPO_ROOT / "hooks" / "_lib" / "shadow-checkpoint-helpers.sh"
HOOK = REPO_ROOT / "hooks" / "shadow-git-checkpoint.sh"
SETTINGS_JSON = REPO_ROOT / "settings.json"
PIPELINE_SKILL_MD = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"
BATCH_PIPELINE_SKILL_MD = REPO_ROOT / "skills" / "batch-pipeline" / "SKILL.md"
PIPELINE_PROTOCOL_MD = REPO_ROOT / "rules" / "_detail" / "pipeline-protocol.md"


def _bash(snippet: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run ``snippet`` with bash, sourcing the helpers module first."""

    full = f'set -euo pipefail; source "{HELPERS}"; {snippet}'
    proc_env = os.environ.copy()
    if env is not None:
        proc_env.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        ["bash", "-c", full],
        env=proc_env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# AC1.1 — _sgc_resolve_worktree
# ---------------------------------------------------------------------------


def test_ac11_resolve_worktree_finds_agent_path(tmp_path: Path) -> None:
    """Echoes worktree absolute path when FILE_PATH is under .claude/worktrees/agent-*."""

    wt = tmp_path / ".claude" / "worktrees" / "agent-1f2c0a"
    (wt / "src").mkdir(parents=True)
    target = wt / "src" / "foo.ts"
    target.write_text("// hi")

    result = _bash(f'_sgc_resolve_worktree "{target}"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(wt.resolve())


def test_ac11_resolve_worktree_empty_when_outside(tmp_path: Path) -> None:
    """Echoes empty + exits 1 when FILE_PATH is not under any agent worktree."""

    repo = tmp_path / "REPO"
    repo.mkdir()
    target = repo / "foo.ts"
    target.write_text("// hi")

    result = _bash(f'_sgc_resolve_worktree "{target}" || echo "RC=$?"')
    assert "RC=1" in result.stdout, result.stdout
    # Stdout before the RC line should be empty (the helper echoed nothing).
    before_rc = result.stdout.split("RC=")[0]
    assert before_rc.strip() == "", before_rc


def test_ac11_resolve_worktree_handles_nonexistent_file(tmp_path: Path) -> None:
    """Write tool may target a not-yet-created file — Python realpath must handle this."""

    wt = tmp_path / ".claude" / "worktrees" / "agent-newfile"
    (wt / "src").mkdir(parents=True)
    target = wt / "src" / "does-not-exist-yet.ts"  # not created

    result = _bash(f'_sgc_resolve_worktree "{target}"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(wt.resolve())


def test_ac11_resolve_worktree_requires_dot_claude_grandparent(tmp_path: Path) -> None:
    """A spurious `worktrees/agent-x/` outside a `.claude/` parent must NOT match."""

    # Construct a deceptive path: <tmp>/random/worktrees/agent-fake/foo.ts
    # The grandparent is `worktrees` and base is `agent-fake`, but the
    # great-grandparent is `random`, not `.claude`.
    fake = tmp_path / "random" / "worktrees" / "agent-fake"
    fake.mkdir(parents=True)
    target = fake / "foo.ts"
    target.write_text("// not a real worktree")

    result = _bash(f'_sgc_resolve_worktree "{target}" || echo "RC=$?"')
    assert "RC=1" in result.stdout, (
        "Spurious worktree-shaped path was incorrectly accepted: " + result.stdout
    )


# ---------------------------------------------------------------------------
# AC1.2 — _sgc_resolve_task_id
# ---------------------------------------------------------------------------


def test_ac12_resolve_task_id_prefers_env_var(tmp_path: Path) -> None:
    """When CLAUDE_PIPELINE_TASK_ID is set, helper echoes it without a fallback shell-out."""

    env = {
        "CLAUDE_PIPELINE_TASK_ID": "shadow-git-checkpoint",
        "TMPDIR": str(tmp_path),
        "CLAUDE_SESSION_ID": "task-id-test",
    }
    result = _bash("_sgc_resolve_task_id", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "shadow-git-checkpoint"


def test_ac12_resolve_task_id_returns_empty_when_no_pipeline(tmp_path: Path) -> None:
    """No env var, no active pipeline → empty + exit 1."""

    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir()
    env = {
        "CLAUDE_PIPELINE_TASK_ID": "",
        "CLAUDE_PIPELINE_STATE_DIR": str(state_dir),
        "TMPDIR": str(tmp_path),
        "CLAUDE_SESSION_ID": "no-pipeline-test",
    }
    result = _bash('_sgc_resolve_task_id || echo "RC=$?"', env=env)
    assert "RC=1" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# AC1.3 — _sgc_validate_id
# ---------------------------------------------------------------------------


def test_ac13_validate_id_accepts_safe_names() -> None:
    for safe in ("shadow-git-checkpoint", "agent-1f2c0a", "task_id.v2", "a", "0"):
        result = _bash(f'_sgc_validate_id "{safe}"')
        assert result.returncode == 0, f"{safe!r} should be valid: {result.stderr}"


def test_ac13_validate_id_rejects_traversal_and_separators() -> None:
    """Reject path-traversal segments, slashes, whitespace, and quotes.

    Hostile values are passed via env vars to avoid shell-quoting pitfalls in
    the test fixture itself (the helper's safety is what's under test).
    """

    hostile = ["../etc", "..", "a/b", "a b", "tab\there", "a\nb", "a;rm -rf /", 'a"b', "''", ""]
    for candidate in hostile:
        result = _bash(
            '_sgc_validate_id "$HOSTILE" || echo "RC=$?"',
            env={"HOSTILE": candidate},
        )
        assert "RC=" in result.stdout, f"{candidate!r} should be rejected, got {result.stdout!r}"


# ---------------------------------------------------------------------------
# AC1.5 — _sgc_ref_name
# ---------------------------------------------------------------------------


def test_ac15_ref_name_builds_when_components_valid() -> None:
    result = _bash('_sgc_ref_name "shadow-git-checkpoint" "agent-1f2c" "0001"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "refs/checkpoints/shadow-git-checkpoint/agent-1f2c-0001"


def test_ac15_ref_name_rejects_invalid_task_id() -> None:
    result = _bash('_sgc_ref_name "../bad" "agent" "0001" || echo "RC=$?"')
    assert "RC=1" in result.stdout, result.stdout
    before_rc = result.stdout.split("RC=")[0]
    assert before_rc.strip() == "", before_rc


def test_ac15_ref_name_rejects_invalid_slug() -> None:
    result = _bash('_sgc_ref_name "task" "agent/.." "0001" || echo "RC=$?"')
    assert "RC=1" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# AC2.8 — mechanical grep: every git invocation uses git -C "$WT" delegation
# ---------------------------------------------------------------------------


_READ_ONLY_VERBS = ("for-each-ref", "rev-parse")


def _git_lines_in(path: Path) -> list[str]:
    """Return every non-comment line that contains a `git ` invocation."""

    out = []
    for raw in path.read_text().splitlines():
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        if " git " not in f" {raw} " and not raw.lstrip().startswith("git "):
            continue
        out.append(raw)
    return out


def test_ac28_all_git_invocations_use_dash_C_delegation() -> None:
    """No bare `git <verb>` invocations in hook or helpers (Iron Law 4)."""

    offenders = []
    for path in (HOOK, HELPERS):
        if not path.exists():
            pytest.fail(f"{path} not yet created — Slice {path.name} must land first")
        for line in _git_lines_in(path):
            if 'git -C "$' in line:
                continue
            if any(verb in line for verb in _READ_ONLY_VERBS):
                # Read-only verbs are safe even without -C delegation.
                continue
            offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, "Bare git invocations found:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# AC2.11 — JSONL injection guard: no printf-with-%s into a JSON object
# ---------------------------------------------------------------------------


def test_ac211_jsonl_emission_uses_python_json_dumps() -> None:
    """No `printf '{...}' "$var"` style JSON construction in hook or helpers."""

    pattern_offenders = []
    for path in (HOOK, HELPERS):
        if not path.exists():
            pytest.fail(f"{path} not yet created")
        text = path.read_text()
        # Look for printf '{ ... %s ...' patterns — the canonical injection footgun.
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "printf" not in stripped:
                continue
            if "{" in stripped and "%s" in stripped and ('"' in stripped or "'" in stripped):
                pattern_offenders.append(f"{path.name}: {line.strip()}")
    assert not pattern_offenders, (
        "JSONL via printf detected — use python3 json.dumps:\n"
        + "\n".join(pattern_offenders)
    )


# ---------------------------------------------------------------------------
# AC3 — settings.json wiring
# ---------------------------------------------------------------------------


def _load_settings() -> dict:
    return json.loads(SETTINGS_JSON.read_text())


def _post_tool_use_blocks() -> list[dict]:
    return _load_settings().get("hooks", {}).get("PostToolUse", [])


def test_ac31_settings_json_has_new_matcher() -> None:
    """settings.json carries a Write|Edit|NotebookEdit matcher firing the new hook."""

    matched = [
        block
        for block in _post_tool_use_blocks()
        if block.get("matcher") == "Write|Edit|NotebookEdit"
    ]
    assert len(matched) == 1, (
        f"Expected exactly one Write|Edit|NotebookEdit block, got {len(matched)}"
    )
    block = matched[0]
    cmds = [hk.get("command", "") for hk in block.get("hooks", []) if hk.get("type") == "command"]
    assert any("shadow-git-checkpoint.sh" in cmd for cmd in cmds), cmds
    timeouts = [hk.get("timeout") for hk in block.get("hooks", []) if hk.get("type") == "command"]
    assert 5000 in timeouts, timeouts


def test_ac32_existing_matcher_blocks_untouched() -> None:
    """Other PostToolUse matcher blocks (Write, Edit, Bash, unmatchered) survive untouched."""

    matchers = [block.get("matcher", "") for block in _post_tool_use_blocks()]
    assert "Write" in matchers, matchers
    assert "Edit" in matchers, matchers
    assert "Bash" in matchers, matchers
    # At least one unmatchered (universal) block must still exist for tool-timing-capture etc.
    assert "" in matchers, matchers


def test_ac33_uses_portable_config_dir() -> None:
    """The new shadow-git-checkpoint.sh entry uses ${CLAUDE_CONFIG_DIR:-$HOME/.claude}."""

    text = SETTINGS_JSON.read_text()
    new_entry_lines = [
        line for line in text.splitlines() if "shadow-git-checkpoint.sh" in line
    ]
    assert new_entry_lines, "shadow-git-checkpoint.sh entry missing from settings.json"
    for line in new_entry_lines:
        assert "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" in line, line
        assert "~/.claude" not in line, line  # never a bare home expansion


# ---------------------------------------------------------------------------
# AC4.1 — Pipeline SKILL.md Step 7d carries ref cleanup snippet
# ---------------------------------------------------------------------------


def test_ac41_pipeline_skill_step7d_has_ref_cleanup() -> None:
    text = PIPELINE_SKILL_MD.read_text()
    assert "refs/checkpoints" in text, "Step 7d snippet missing refs/checkpoints reference"
    assert "update-ref -d" in text, "Step 7d snippet missing update-ref -d call"


# ---------------------------------------------------------------------------
# AC5.1 / AC5.2 — pipeline-protocol.md doc-surface
# ---------------------------------------------------------------------------


def test_ac51_pipeline_protocol_mentions_checkpoint_refs() -> None:
    text = PIPELINE_PROTOCOL_MD.read_text()
    assert "refs/checkpoints" in text, "pipeline-protocol.md missing refs/checkpoints contract"


def test_ac52_dual_path_soak_section_documents_ref_cleanup() -> None:
    text = PIPELINE_PROTOCOL_MD.read_text().lower()
    assert "shadow checkpoint" in text or "shadow-checkpoint" in text or "checkpoint ref" in text, (
        "DUAL_PATH soak section missing ref-cleanup mention"
    )


# ---------------------------------------------------------------------------
# AC5.3 — batch-pipeline SKILL.md mentions ref cleanup delegation
# ---------------------------------------------------------------------------


def test_ac53_batch_pipeline_skill_documents_ref_cleanup() -> None:
    text = BATCH_PIPELINE_SKILL_MD.read_text().lower()
    assert "checkpoint" in text, "batch-pipeline SKILL.md missing checkpoint mention"


# ---------------------------------------------------------------------------
# AC6.4 — eval cases exist
# ---------------------------------------------------------------------------


def test_ac64_eval_cases_exist() -> None:
    base = REPO_ROOT / "eval" / "cases"
    happy = base / "shadow-git-checkpoint-happy-path"
    traversal = base / "shadow-git-checkpoint-traversal-rejection"
    for case in (happy, traversal):
        assert case.is_dir(), f"missing eval case directory: {case}"
        assert (case / "metadata.json").exists(), f"{case} missing metadata.json"
        assert (case / "task.md").exists(), f"{case} missing task.md"
        assert (case / "expected.md").exists(), f"{case} missing expected.md"
