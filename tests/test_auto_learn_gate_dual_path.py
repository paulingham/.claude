"""Slice B — auto_learn_gate.current_pipeline_id supports new layout. AC #5."""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "hooks" / "_lib"


def _run_current_pipeline_id(home: Path) -> str:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["HARNESS_DATA"] = str(home / ".claude")
    env.pop("CLAUDE_PLUGIN_DATA", None)
    env.pop("CLAUDE_CONFIG_DIR", None)
    result = subprocess.run(
        [sys.executable, "-c", "import auto_learn_gate; print(auto_learn_gate.current_pipeline_id())"],
        capture_output=True, text=True, env={**env, "PYTHONPATH": str(LIB)}, timeout=15,
    )
    return result.stdout.strip()


def test_current_pipeline_id_finds_new_layout(tmp_path):
    state = tmp_path / ".claude" / "pipeline-state" / "t-new"
    state.mkdir(parents=True)
    (state / "pipeline.md").write_text("---\ntask_id: t-new\nverdict: in_progress\n---\n")
    assert _run_current_pipeline_id(tmp_path) == "t-new"
