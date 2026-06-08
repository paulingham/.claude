"""Slice C — Reflect cleanup tests.

Reflect cleanup is dual-form during the DUAL_PATH soak:
  1. `rm -rf pipeline-state/{task-id}/` removes the new-layout subdir in one op.
  2. Iterate `_psp_phase_list` and remove legacy `{task-id}-{phase}.md` files
     (NEVER use bare `pipeline-state/{task-id}-*.md` globs — that matches
     prefix neighbours).

These tests exercise the canonical cleanup procedure that
`skills/pipeline/SKILL.md` Step 7 documents. They source the bash helper
to read `_psp_phase_list` and execute the documented cleanup snippet.
"""
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "hooks/_lib/pipeline-state-paths.sh"
PIPELINE_SKILL = REPO_ROOT / "skills/pipeline/SKILL.md"


# Canonical cleanup snippet — mirrors what skills/pipeline/SKILL.md Step 7
# documents. Dual-form: rm -rf the subdir AND iterate _psp_phase_list to
# delete legacy files. NEVER `pipeline-state/{task-id}-*.md` (bare glob).
CLEANUP_SNIPPET = r'''
source "{helper}"
state_dir="{state_dir}"
task="{task}"
ws="{ws}"
# Form 1: subdir cleanup (new layout).
if [ -n "$ws" ]; then
  rm -rf "$state_dir/workstreams/$ws/$task"
else
  rm -rf "$state_dir/$task"
fi
# Form 2: legacy phase enumeration (no bare globs).
while IFS= read -r phase; do
  if [ -n "$ws" ]; then
    rm -f "$state_dir/workstreams/$ws/$task-$phase.md"
  else
    rm -f "$state_dir/$task-$phase.md"
  fi
done < <(_psp_phase_list)
# Approval token + trajectory (well-known names, not phases).
if [ -n "$ws" ]; then
  rm -f "$state_dir/workstreams/$ws/$task-approval.token" \
        "$state_dir/workstreams/$ws/$task-trajectory.jsonl"
else
  rm -f "$state_dir/$task-approval.token" "$state_dir/$task-trajectory.jsonl"
fi
'''


def _run_cleanup(state_dir: Path, task_id: str, workstream: str = "") -> tuple[int, str, str]:
    snippet = CLEANUP_SNIPPET.format(
        helper=HELPER, state_dir=state_dir, task=task_id, ws=workstream
    )
    proc = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _make_legacy(state_dir: Path, task_id: str, phases: list[str]) -> list[Path]:
    paths = []
    for p in phases:
        path = state_dir / f"{task_id}-{p}.md"
        path.write_text(f"---\ntask_id: {task_id}\nphase: {p}\n---\n")
        paths.append(path)
    return paths


def _make_subdir(state_dir: Path, task_id: str, phases: list[str]) -> Path:
    sub = state_dir / task_id
    sub.mkdir(parents=True, exist_ok=True)
    for p in phases:
        (sub / f"{p}.md").write_text(f"---\ntask_id: {task_id}\nphase: {p}\n---\n")
    return sub


def test_reflect_cleanup_removes_subdir_in_one_op(tmp_path):
    # Behavioural: the canonical cleanup snippet removes the subdir.
    sub = _make_subdir(tmp_path, "t1", ["pipeline", "build", "review"])
    assert sub.exists()
    code, _, err = _run_cleanup(tmp_path, "t1")
    assert code == 0, err
    assert not sub.exists()
    # Doc-grep: SKILL.md must document the new-layout subdir cleanup. The
    # command is `find "$task_dir" -type f -delete` (NOT `rm -rf` — that is
    # sandbox-denied on directories even on orchestrator-writable paths).
    skill_text = PIPELINE_SKILL.read_text()
    assert 'find "$task_dir" -type f -delete' in skill_text, \
        ('skills/pipeline/SKILL.md Step 7 must document the per-task subdir '
         'cleanup via `find "$task_dir" -type f -delete`')


def test_reflect_cleanup_does_not_touch_other_tasks(tmp_path):
    _make_subdir(tmp_path, "t1", ["pipeline", "build"])
    other = _make_subdir(tmp_path, "t2", ["pipeline", "build"])
    code, _, err = _run_cleanup(tmp_path, "t1")
    assert code == 0, err
    assert other.exists()
    assert (other / "pipeline.md").exists()
    # Doc-grep: SKILL must NOT document a bare glob like
    # `pipeline-state/{task-id}-*.md` for cleanup (that would match prefix
    # neighbours). R12 mitigation.
    skill_text = PIPELINE_SKILL.read_text()
    assert "pipeline-state/{task-id}-*.md" not in skill_text, \
        "Cleanup must NOT use bare glob `pipeline-state/{task-id}-*.md` (R12 mitigation)"


def test_reflect_cleanup_does_not_match_prefix_neighbors(tmp_path):
    """Cleanup of `tool` must NOT delete `tool-timing-capture-*` legacy files.

    R12 mitigation: explicit phase enumeration, NOT bare globs.
    `tool-timing-capture-pipeline.md` is NOT a `tool` phase file —
    it is a separate task with its own task_id.
    """
    legacy_neighbour = tmp_path / "tool-timing-capture-pipeline.md"
    legacy_neighbour.write_text("---\ntask_id: tool-timing-capture\n---\n")
    legacy_target = _make_legacy(tmp_path, "tool", ["pipeline", "build"])
    code, _, err = _run_cleanup(tmp_path, "tool")
    assert code == 0, err
    for p in legacy_target:
        assert not p.exists(), f"target {p} should be removed"
    assert legacy_neighbour.exists(), "prefix-neighbour must NOT be touched"
    # Doc-grep: SKILL must reference the canonical phase enumeration.
    skill_text = PIPELINE_SKILL.read_text()
    assert "_psp_phase_list" in skill_text, \
        "Cleanup must reference `_psp_phase_list` for explicit phase enumeration"


def test_reflect_cleanup_iterates_canonical_phase_list(tmp_path):
    """Cleanup removes only files matching `_psp_phase_list`.

    Files with arbitrary suffixes (e.g. `{task-id}-random.md`) are left alone
    because they are not in the canonical list. This proves cleanup is
    enumeration-driven, not glob-driven.
    """
    legacy_target = _make_legacy(tmp_path, "t1", ["pipeline", "build", "review", "verify"])
    # Off-list file with same prefix — cleanup must NOT remove it.
    off_list = tmp_path / "t1-arbitrary-suffix.md"
    off_list.write_text("---\ntask_id: t1\n---\n")
    code, _, err = _run_cleanup(tmp_path, "t1")
    assert code == 0, err
    for p in legacy_target:
        assert not p.exists(), f"phase-list file {p} should be removed"
    assert off_list.exists(), "off-list file must NOT be removed"
    # Doc-grep: SKILL must show iteration via `_psp_phase_list` (e.g.
    # `while IFS= read -r phase` ... `_psp_phase_list`).
    skill_text = PIPELINE_SKILL.read_text()
    assert "_psp_phase_list" in skill_text, \
        "SKILL.md must invoke `_psp_phase_list` for cleanup iteration"
