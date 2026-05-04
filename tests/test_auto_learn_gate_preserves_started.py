"""B8.1 fix — auto-learn-gate.sh MUST preserve ``last_learn_started``.

Regression: prior to the fix, every Stop event rebuilt the state file via
``jq -n`` with five keys and stripped ``last_learn_started``. This caused
``is_in_flight`` to flip back to "idle" mid-run, allowing a second ``/learn``
to be spawned while the first was still executing — defeating the queue.

This test simulates ``mark_started`` → auto-learn-gate fire and asserts the
sentinel survives.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "auto-learn-gate.sh"


def _run_hook(env_overrides):
    env = dict(os.environ)
    env.update(env_overrides)
    # Drain stdin (Stop event JSON) — the hook reads via `cat > /dev/null`.
    return subprocess.run(
        ["bash", str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def test_started_sentinel_survives_stop_firing(tmp_path):
    # Arrange: a fake project-hash dir with .learn-state.json carrying
    # last_learn_started but no last_learn_run (the in-flight window).
    home = tmp_path / "home"
    learning_dir = home / ".claude" / "learning" / "fixture-hash"
    (learning_dir / "instincts").mkdir(parents=True)
    state = learning_dir / ".learn-state.json"
    sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
    import learn_status
    learn_status.mark_started(state, "2026-05-04T10:00:00Z")
    pre = json.loads(state.read_text())
    assert pre["last_learn_started"] == "2026-05-04T10:00:00Z"

    # Act: fire the Stop hook with the test override pointing at our hash.
    # CLAUDE_CONFIG_DIR points at the worktree so the hook's library sources
    # resolve; HOME is the fake fixture root so the state file lands under
    # tmp_path/.claude/learning/fixture-hash/ (matched by CLAUDE_LEARN_TEST_HASH).
    result = _run_hook({
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(REPO_ROOT),
        "CLAUDE_LEARN_TEST_HASH": "fixture-hash",
        # Disable the cross-process flock so the hook runs deterministically
        # under pytest without /tmp lock contention from a parallel session.
        "CLAUDE_LEARNING_FLOCK_DISABLE": "1",
        "CLAUDE_HOOK_PROFILE": "standard",
    })

    # Assert: hook exited cleanly, sentinel is preserved.
    assert result.returncode == 0, (
        f"hook exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    post = json.loads(state.read_text())
    assert post["last_learn_started"] == "2026-05-04T10:00:00Z", (
        f"last_learn_started stripped by Stop firing: {post}"
    )
    # And the predicate must still report in-flight.
    assert learn_status.is_in_flight(post)
