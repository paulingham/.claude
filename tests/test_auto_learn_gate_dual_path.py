"""Slice B — auto-learn-gate-core's _alg_current_pipeline_id supports new layout. AC #4."""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = REPO_ROOT / "hooks" / "_lib" / "auto-learn-gate-core.sh"


def _run_alg_current_pipeline_id(home: Path) -> str:
    env = dict(os.environ); env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", "-c", f"source '{CORE_LIB}' && _alg_current_pipeline_id"],
        capture_output=True, text=True, env=env, timeout=15,
    )
    return result.stdout.strip()


def test_current_pipeline_id_finds_new_layout(tmp_path):
    state = tmp_path / ".claude" / "pipeline-state" / "t-new"
    state.mkdir(parents=True)
    (state / "pipeline.md").write_text("---\ntask_id: t-new\nverdict: in_progress\n---\n")
    assert _run_alg_current_pipeline_id(tmp_path) == "t-new"
