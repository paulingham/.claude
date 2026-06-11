"""GP-K1 — unit tests for hooks/_lib/auto_learn_gate.py.

The module subsumes the gate-decision, state-advance, and in-process
re-entrancy-lock logic previously split across auto-learn-gate-core.sh,
auto-learn-state.sh, and auto-learn-lock.sh. These tests pin:

  - should_fire truth table (obs floor, hours gate, cur==fired suppression)
  - hours_since ISO parse + null/garbage → 999 (kills the bash date divergence)
  - current_pipeline_id new-layout / legacy-layout / none
  - run(): fire path, not-met path (no trigger stdout), offset advance,
    pipelines bump, B8.1 last_learn_started preservation
  - fcntl-based concurrent run serialization
  - log rotation when the gate log exceeds 1 MiB
"""
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import auto_learn_gate  # noqa: E402  (path inserted above)
import learn_status  # noqa: E402


def _write_state(state_path, **fields):
    base = {
        "last_learn_run": None,
        "last_learn_started": None,
        "pipelines_since_learn": 0,
        "observations_since_learn": 0,
        "last_fired_pipeline_id": None,
        "last_observation_offset": 0,
    }
    base.update(fields)
    Path(state_path).write_text(json.dumps(base))


def _pipeline_record(pipeline_id):
    return json.dumps({"record_type": "pipeline", "pipeline_id": pipeline_id,
                       "phases": ["plan"]})


# --- should_fire truth table ----------------------------------------------

def test_should_fire_false_below_observation_floor():
    assert auto_learn_gate.should_fire(2, 9, None, "p1", "") is False


def test_should_fire_true_when_last_run_null_and_obs_met():
    assert auto_learn_gate.should_fire(3, 0, None, "p1", "") is True


def test_should_fire_false_when_no_gate_dimension_met():
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    assert auto_learn_gate.should_fire(5, 1, recent, "p1", "") is False


def test_should_fire_true_when_pipelines_reach_three():
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    assert auto_learn_gate.should_fire(5, 3, recent, "p1", "") is True


def test_should_fire_true_when_hours_since_exceeds_twenty_four():
    assert auto_learn_gate.should_fire(5, 0, "2000-01-01T00:00:00Z", "p1", "") is True


def test_should_fire_false_when_current_pipeline_already_fired():
    assert auto_learn_gate.should_fire(5, 9, None, "p1", "p1") is False


# --- hours_since -----------------------------------------------------------

def test_hours_since_null_string_returns_sentinel():
    assert auto_learn_gate.hours_since("null") == 999


def test_hours_since_empty_returns_sentinel():
    assert auto_learn_gate.hours_since("") == 999


def test_hours_since_garbage_returns_sentinel():
    assert auto_learn_gate.hours_since("not-a-timestamp") == 999


def test_hours_since_parses_well_formed_past_timestamp():
    assert auto_learn_gate.hours_since("2000-01-01T00:00:00Z") >= 24


# --- current_pipeline_id ---------------------------------------------------

def _harness_env(home):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["HARNESS_DATA"] = str(home / ".claude")
    env.pop("CLAUDE_PLUGIN_DATA", None)
    env.pop("CLAUDE_CONFIG_DIR", None)
    return env


def _seed_new_layout(home, task_id):
    state = home / ".claude" / "pipeline-state" / task_id
    state.mkdir(parents=True)
    (state / "pipeline.md").write_text(
        f"---\ntask_id: {task_id}\nverdict: in_progress\n---\n")


def _seed_legacy_layout(home, task_id):
    state = home / ".claude" / "pipeline-state"
    state.mkdir(parents=True)
    (state / f"{task_id}-pipeline.md").write_text(
        f"---\ntask_id: {task_id}\nverdict: in_progress\n---\n")


def test_current_pipeline_id_finds_new_layout(tmp_path, monkeypatch):
    _seed_new_layout(tmp_path, "t-new")
    monkeypatch.setattr(os, "environ", _harness_env(tmp_path))
    assert auto_learn_gate.current_pipeline_id() == "t-new"


def test_current_pipeline_id_finds_legacy_layout(tmp_path, monkeypatch):
    _seed_legacy_layout(tmp_path, "t-legacy")
    monkeypatch.setattr(os, "environ", _harness_env(tmp_path))
    assert auto_learn_gate.current_pipeline_id() == "t-legacy"


def test_current_pipeline_id_returns_empty_when_none(tmp_path, monkeypatch):
    (tmp_path / ".claude" / "pipeline-state").mkdir(parents=True)
    monkeypatch.setattr(os, "environ", _harness_env(tmp_path))
    assert auto_learn_gate.current_pipeline_id() == ""


# --- run() -----------------------------------------------------------------

def _run_paths(tmp_path):
    state = tmp_path / ".learn-state.json"
    obs = tmp_path / "observations.jsonl"
    log = tmp_path / ".learn-gate.log"
    return state, obs, log


def test_run_fires_and_advances_last_fired(tmp_path, capsys):
    state, obs, log = _run_paths(tmp_path)
    _write_state(state, observations_since_learn=5, pipelines_since_learn=3)
    obs.write_text("")
    auto_learn_gate.run(str(state), str(obs), str(log))
    out = capsys.readouterr().out
    assert "Triggered" in out
    assert not log.exists()


def test_run_not_met_emits_no_trigger_and_logs(tmp_path, capsys):
    state, obs, log = _run_paths(tmp_path)
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_state(state, observations_since_learn=1, last_learn_run=recent)
    obs.write_text("")
    auto_learn_gate.run(str(state), str(obs), str(log))
    out = capsys.readouterr().out
    assert "Triggered" not in out
    assert "gate=not-met" in log.read_text()


def test_run_advances_offset_to_observation_size(tmp_path):
    state, obs, log = _run_paths(tmp_path)
    _write_state(state)
    obs.write_text(_pipeline_record("p1") + "\n")
    auto_learn_gate.run(str(state), str(obs), str(log))
    after = json.loads(state.read_text())
    assert after["last_observation_offset"] == obs.stat().st_size


def test_run_bumps_pipelines_on_new_record(tmp_path):
    state, obs, log = _run_paths(tmp_path)
    _write_state(state, pipelines_since_learn=0)
    obs.write_text(_pipeline_record("p-new") + "\n")
    auto_learn_gate.run(str(state), str(obs), str(log))
    after = json.loads(state.read_text())
    assert after["pipelines_since_learn"] == 1


def test_run_preserves_last_learn_started(tmp_path):
    state, obs, log = _run_paths(tmp_path)
    _write_state(state, observations_since_learn=5, pipelines_since_learn=3,
                 last_learn_started="2026-05-04T10:00:00Z")
    obs.write_text("")
    auto_learn_gate.run(str(state), str(obs), str(log))
    after = json.loads(state.read_text())
    assert after["last_learn_started"] == "2026-05-04T10:00:00Z"


# --- concurrent run serialization (fcntl) ----------------------------------

def _slow_lock_hold(barrier_dir):
    marker = Path(barrier_dir) / "events"
    state = Path(barrier_dir) / ".learn-state.json"
    with auto_learn_gate._lock(str(state)):
        with marker.open("a") as f:
            f.write(f"start {time.time_ns()}\n")
        time.sleep(1.0)
        with marker.open("a") as f:
            f.write(f"end {time.time_ns()}\n")


def test_concurrent_runs_serialize_on_sidecar_lock(tmp_path):
    barrier = str(tmp_path)
    procs = [multiprocessing.Process(target=_slow_lock_hold, args=(barrier,))
             for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=10)
    events = (tmp_path / "events").read_text().splitlines()
    assert events[0].startswith("start")
    assert events[1].startswith("end")
    assert events[2].startswith("start")


# --- log rotation ----------------------------------------------------------

def test_log_rotates_over_one_mebibyte(tmp_path):
    state, obs, log = _run_paths(tmp_path)
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_state(state, observations_since_learn=1, last_learn_run=recent)
    obs.write_text("")
    log.write_text("x" * (1048576 + 1))
    auto_learn_gate.run(str(state), str(obs), str(log))
    assert (tmp_path / ".learn-gate.log.1").exists()
