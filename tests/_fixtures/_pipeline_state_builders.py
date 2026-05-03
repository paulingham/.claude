"""Path-construction + file-writing helpers for `pipeline_state` fixture.

Kept separate so `pipeline_state.py` stays under the file-line cap.
"""
from pathlib import Path
from typing import Optional


def build_phase_path(state_dir: Path, task_id: str, phase: str,
                     layout: str, workstream: Optional[str]) -> Path:
    """Construct the on-disk path for a single phase artefact."""
    root = _ws_root(Path(state_dir), workstream)
    if layout == "new":
        return root / task_id / f"{phase}.md"
    return root / f"{task_id}-{phase}.md"


def write_state_file(path: Path, task_id: str, phase: str,
                     verdict: str) -> None:
    """Create parent + write a minimal frontmatter pipeline-state file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"task_id: {task_id}\n"
        f"phase: {phase}\n"
        f"verdict: {verdict}\n"
        "---\n"
    )


def _ws_root(state_dir: Path, workstream: Optional[str]) -> Path:
    """Workstream root or plain state_dir; '' and None both mean root."""
    if workstream:
        return state_dir / "workstreams" / workstream
    return state_dir
