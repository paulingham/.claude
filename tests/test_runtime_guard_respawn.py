"""Runtime-guard re-spawn cap tests (wave4-S AC1, AC2, AC7).

Source: pipeline-state/wave4-S-plan.md → AC1 / AC2 / AC7
Origin: pipeline-state/wave4-R-forensics.md anomaly #1 (33-spawn loop)

These tests pin the new re-spawn counter logic in runtime-guard.sh:
- AC1: 4th spawn of same (subagent_type, task_id) blocks (exit 2) with
  a "re-dispatch cap exceeded" stderr message naming both fields.
- AC2: counter file lives at metrics/$SID/subagent-runtimes/<key>.count
  (sibling of .start, NOT under any respawn-counts/ directory).
- AC7: SubagentStop hook does NOT clear .count — only .start. The 4th
  spawn after a Stop event STILL blocks. Pins the cleanup-direction
  policy that fixes the F3 corrected race-window analysis.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "runtime-guard.sh"
STOP_HOOK = REPO_ROOT / "hooks" / "subagent-stop-trajectory.sh"


def _agent_payload(subagent_type="qa-engineer", name=None, team_name=None):
    tool_input = {"subagent_type": subagent_type}
    if name is not None:
        tool_input["name"] = name
    if team_name is not None:
        tool_input["team_name"] = team_name
    return {"tool_name": "Agent", "tool_input": tool_input}


def _bash_payload(command="echo hello"):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(hook_path, payload, env=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env = {**os.environ, "PYTHONPATH": merged_pp,
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["bash", str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=proc_env,
    )


def _make_pipeline_state(state_dir, task_id):
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / f"{task_id}-pipeline.md"
    p.write_text(
        "---\n"
        f"task_id: {task_id}\n"
        "phase: build\n"
        "verdict: in_progress\n"
        "---\n"
    )
    return p


class _RespawnCapBase(unittest.TestCase):
    """Shared isolated-pipeline-state setup for respawn-cap tests."""

    label = "shared"
    task_id = "wave4S-test-shared"

    def setUp(self):
        self.session = f"test-{self.label}-{uuid.uuid4().hex[:8]}"
        self.state_dir = Path(tempfile.mkdtemp(prefix="ps-"))
        self.plugin_data = Path(tempfile.mkdtemp(prefix="pd-"))
        _make_pipeline_state(self.state_dir, self.task_id)
        # Also seed pipeline-state inside plugin_data so the stop hook can
        # discover the active task via HARNESS_DATA/pipeline-state.
        _make_pipeline_state(self.plugin_data / "pipeline-state", self.task_id)
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_PIPELINE_STATE_DIR": str(self.state_dir),
            "CLAUDE_PIPELINE_TASK_ID": self.task_id,
            "HOME": str(self.plugin_data),
            "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
        }

    def tearDown(self):
        shutil.rmtree(self.state_dir, ignore_errors=True)
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def runtime_dir(self):
        return self.plugin_data / "metrics" / self.session / "subagent-runtimes"


class RespawnCapBlocksFourthSpawn(_RespawnCapBase):
    """AC1: 4th spawn of same key exits 2 with cap message naming both fields."""

    label = "respawn"
    task_id = "wave4S-test-cap"

    def test_fourth_spawn_same_key_exits_two_with_cap_message(self):
        payload = _agent_payload(subagent_type="qa-engineer")
        for i in range(3):
            r = _run_hook(HOOK, payload, env=self.env)
            self.assertEqual(r.returncode, 0, f"spawn {i + 1} unexpected: {r.stderr}")
        r4 = _run_hook(HOOK, payload, env=self.env)
        self.assertEqual(r4.returncode, 2, f"4th spawn must block: stderr={r4.stderr}")
        self.assertIn("re-dispatch cap exceeded", r4.stderr)
        self.assertIn("subagent_type=qa-engineer", r4.stderr)
        self.assertIn(f"task_id={self.task_id}", r4.stderr)


class RespawnCounterPersistsToSubagentRuntimesDir(_RespawnCapBase):
    """AC2: counter file is sibling of .start under subagent-runtimes/."""

    label = "cnt"
    task_id = "wave4S-test-cnt"

    def test_counter_persists_to_subagent_runtimes_dir(self):
        payload = _agent_payload(subagent_type="software-engineer")
        for _ in range(2):
            r = _run_hook(HOOK, payload, env=self.env)
            self.assertEqual(r.returncode, 0)
        count_files = list(self.runtime_dir().glob("*.count"))
        self.assertEqual(
            len(count_files), 1,
            f"expected exactly one .count file in {self.runtime_dir()}, got {count_files}",
        )
        self.assertEqual(count_files[0].read_text().strip(), "2")
        # Regression guard: no respawn-counts/ directory anywhere
        wrong = self.plugin_data / "metrics" / self.session / "respawn-counts"
        self.assertFalse(
            wrong.exists(),
            f"respawn-counts/ must not be created (legacy mis-spec): {wrong}",
        )


class SubagentStopDoesNotClearRespawnCounter(_RespawnCapBase):
    """AC7: SubagentStop clears .start but NOT .count; 4th spawn still blocks."""

    label = "keep"
    task_id = "wave4S-keep-cnt"

    def test_subagent_stop_does_not_clear_respawn_counter(self):
        payload = _agent_payload(subagent_type="code-reviewer")
        for _ in range(3):
            r = _run_hook(HOOK, payload, env=self.env)
            self.assertEqual(r.returncode, 0)
        starts = list(self.runtime_dir().glob("*.start"))
        counts = list(self.runtime_dir().glob("*.count"))
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(counts), 1)
        # Invoke SubagentStop with matching subagent_type
        stop_payload = {"subagent_type": "code-reviewer"}
        r_stop = _run_hook(STOP_HOOK, stop_payload, env=self.env)
        self.assertEqual(r_stop.returncode, 0, f"stop hook failed: {r_stop.stderr}")
        # .start must be removed; .count must remain at 3
        starts_after = list(self.runtime_dir().glob("*.start"))
        counts_after = list(self.runtime_dir().glob("*.count"))
        self.assertEqual(
            len(starts_after), 0, f".start should be cleared: {starts_after}"
        )
        self.assertEqual(
            len(counts_after), 1, f".count must persist: {counts_after}"
        )
        self.assertEqual(counts_after[0].read_text().strip(), "3")
        # Spawn a 4th time — STILL blocks (cap policy survived stop event)
        r4 = _run_hook(HOOK, payload, env=self.env)
        self.assertEqual(
            r4.returncode, 2,
            f"4th spawn after stop must STILL block: stderr={r4.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
