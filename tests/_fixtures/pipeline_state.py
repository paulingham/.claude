"""Slice E.5 — pipeline-state fixture helper for tests.

`make_pipeline_fixture(state_dir, task_id, *, layout, workstream, phases,
verdict)` materialises a pipeline-state tree under either layout. Tests
swap bespoke `mkdir`/`touch`/`write_text` snippets for one call.

DUAL_PATH soak supports both layouts:
- `layout="new"`  → `pipeline-state/{task}/{phase}.md`
- `layout="legacy"` → `pipeline-state/{task}-{phase}.md`

Returns the path to the pipeline-md file (or legacy `{task}-pipeline.md`).
"""
from pathlib import Path
from typing import List, Optional

from ._pipeline_state_builders import build_phase_path, write_state_file

DEFAULT_PHASES = ("pipeline",)


def make_pipeline_fixture(
    state_dir: Path,
    task_id: str,
    *,
    layout: str = "new",
    workstream: Optional[str] = None,
    phases: Optional[List[str]] = None,
    verdict: str = "in_progress",
) -> Path:
    """Materialise a pipeline-state fixture; return path to pipeline-md."""
    _validate_layout(layout)
    selected = list(phases) if phases else list(DEFAULT_PHASES)
    pipeline_path = None
    for phase in selected:
        path = build_phase_path(state_dir, task_id, phase, layout, workstream)
        write_state_file(path, task_id, phase, verdict)
        if phase == "pipeline":
            pipeline_path = path
    return pipeline_path or build_phase_path(
        state_dir, task_id, "pipeline", layout, workstream)


def _validate_layout(layout: str) -> None:
    if layout not in ("new", "legacy"):
        raise ValueError(f"layout must be 'new' or 'legacy', got: {layout!r}")
