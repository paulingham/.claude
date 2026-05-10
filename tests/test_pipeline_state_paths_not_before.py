"""Slice slice-c-consumer carryforward — `_psp_find_active_pipelines` filters
out pipeline-state files whose `not_before` frontmatter is in the future.

The slice-d soak placeholder sets `not_before: 2026-08-08T00:00:00Z`. Until
the date passes, SessionStart's active-pipeline scan must NOT surface the
file (that would re-enter `/pipeline-resume` for a pipeline not yet ready).
After the date passes, the file appears in the active list.

Strategy: drive `find_pipeline_files` (the Python bridge `_psp_find_active_pipelines`
delegates to) with a controllable wall-clock via `now_unix=...`. Falls back to
`time.time()` when omitted, preserving today's behaviour.
"""
import time
from pathlib import Path

import pytest

from pipeline_state_paths import find_pipeline_files


def _write_pipeline(state_dir: Path, task: str, frontmatter: str) -> Path:
    task_dir = state_dir / task
    task_dir.mkdir(parents=True, exist_ok=True)
    p = task_dir / "pipeline.md"
    p.write_text(f"---\n{frontmatter}\n---\n\n# {task}\n")
    return p


def test_active_list_excludes_future_not_before(tmp_path: Path) -> None:
    """File with `not_before` in the future is excluded from the active list."""
    future = "2026-08-08T00:00:00Z"
    soak = _write_pipeline(
        tmp_path,
        "wave-dag-soak-end",
        f"task_id: wave-dag-soak-end\nphase: pipeline\n"
        f"not_before: {future}\nweekly_resurface: true",
    )
    live = _write_pipeline(
        tmp_path,
        "live-task",
        "task_id: live-task\nphase: build",
    )
    # Mock now to a date BEFORE not_before.
    fixed_now = 1715040000  # 2024-05-07 — well before 2026-08-08.
    found = find_pipeline_files(tmp_path, now_unix=fixed_now)
    assert live in found
    assert soak not in found, (
        "Soak placeholder with future not_before must be excluded "
        "from active pipelines until the date passes"
    )


def test_active_list_includes_past_not_before(tmp_path: Path) -> None:
    """Once `not_before` has passed, the file rejoins the active list."""
    past = "2024-01-01T00:00:00Z"
    soak = _write_pipeline(
        tmp_path,
        "old-soak-end",
        f"task_id: old-soak-end\nphase: pipeline\nnot_before: {past}",
    )
    fixed_now = 1715040000  # 2024-05-07 — well after 2024-01-01.
    found = find_pipeline_files(tmp_path, now_unix=fixed_now)
    assert soak in found


def test_active_list_handles_missing_not_before(tmp_path: Path) -> None:
    """Files without `not_before` are unaffected — today's behaviour preserved."""
    p = _write_pipeline(tmp_path, "ordinary", "task_id: ordinary\nphase: build")
    found = find_pipeline_files(tmp_path)  # no now_unix — uses time.time()
    assert p in found


def test_active_list_handles_malformed_not_before(tmp_path: Path) -> None:
    """Unparseable `not_before` is treated as missing (fail-open)."""
    p = _write_pipeline(
        tmp_path,
        "bad-date",
        "task_id: bad-date\nphase: build\nnot_before: not-a-date",
    )
    found = find_pipeline_files(tmp_path, now_unix=time.time())
    assert p in found, "malformed not_before must NOT silently exclude the file"


def test_active_list_resurfaces_at_exact_boundary(tmp_path: Path) -> None:
    """At now_unix == not_before_unix, the file becomes active (>=, not >)."""
    # 2026-08-08T00:00:00Z = 1786147200 unix seconds.
    boundary_iso = "2026-08-08T00:00:00Z"
    boundary_unix = 1786147200
    p = _write_pipeline(
        tmp_path,
        "boundary",
        f"task_id: boundary\nphase: pipeline\nnot_before: {boundary_iso}",
    )
    # One second before — excluded.
    assert p not in find_pipeline_files(tmp_path, now_unix=boundary_unix - 1)
    # At/after the boundary — included.
    assert p in find_pipeline_files(tmp_path, now_unix=boundary_unix)
    assert p in find_pipeline_files(tmp_path, now_unix=boundary_unix + 1)
