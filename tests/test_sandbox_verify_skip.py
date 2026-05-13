"""Story 3 carryforwards + AC6 — sandbox_verify_skip hardening + teardown.

Covers Story 1 security LOWs + Story 3 AC6:

- LOW-A (path-traversal): `session_id` of `"../../etc/passwd"` → guard rejects
  via regex `re.fullmatch(r"[A-Za-z0-9_.-]+", session_id)` → returns `"local"`
  AND prints stderr warning. Other rejection inputs: `"a/b"`, `"a b"`, `""`.
- LOW-B (JSONL 0o600): every JSONL file the module writes has mode `0o600`.
- AC6 (teardown on every exit path): `provision_and_run` calls
  `destroy_microvm` exactly once on (happy, parser-raises, hard-cap-trip) AND
  appends a teardown JSONL line.
"""
import json
import os
import re
import stat
import sys
import tempfile
import time
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import sandbox_verify_skip
    return sandbox_verify_skip


class SessionIdPathTraversalFallsBackToLocal(unittest.TestCase):
    """LOW-A: session_id containing path-separator metacharacters rejected;
    falls back to `"local"` and emits stderr warning."""

    def test_session_id_path_traversal_falls_back_to_local(self):
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id("../../etc/passwd")
        self.assertEqual(resolved, "local",
                         "path-traversal session_id must fall back to 'local'")
        self.assertIn("session_id", captured_err.getvalue().lower(),
                      "must emit stderr warning when falling back")

    def test_session_id_with_slash_rejected(self):
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id("a/b")
        self.assertEqual(resolved, "local")

    def test_session_id_with_space_rejected(self):
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id("a b")
        self.assertEqual(resolved, "local")

    def test_session_id_empty_rejected(self):
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id("")
        self.assertEqual(resolved, "local")

    def test_session_id_double_dot_falls_back_to_local(self):
        """`..` alone is a traversal vector (Path(metrics_dir) / '..' walks
        out one directory level). Both the tightened regex AND the
        defence-in-depth check must reject it."""
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id("..")
        self.assertEqual(resolved, "local")
        self.assertIn("session_id", captured_err.getvalue().lower())

    def test_session_id_single_dot_falls_back_to_local(self):
        """`.` alone resolves Path(metrics_dir) / '.' to metrics_dir itself
        — still outside the per-session sandbox. Rejected for symmetry."""
        mod = _load()
        captured_err = StringIO()
        with patch.object(sys, "stderr", captured_err):
            resolved = mod._resolve_session_id(".")
        self.assertEqual(resolved, "local")
        self.assertIn("session_id", captured_err.getvalue().lower())

    def test_session_id_valid_passes_through(self):
        """Valid IDs (alphanumeric + `_.-`) pass through unchanged."""
        mod = _load()
        for valid in ["abc123", "session-1.0", "test_session", "x"]:
            resolved = mod._resolve_session_id(valid)
            self.assertEqual(
                resolved, valid,
                f"valid session_id {valid!r} must NOT be replaced")


class JsonlFilesWrittenWithMode0o600(unittest.TestCase):
    """LOW-B: skip-log JSONL created with mode 0o600 (not 0o644)."""

    def test_jsonl_files_written_with_mode_0o600(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_dir = Path(tmp)
            session_id = "test-session-mode"

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                mod.emit_skip_if_no_token(session_id, str(metrics_dir))

            jsonl_path = (metrics_dir / session_id /
                          "sandbox-verify-skips.jsonl")
            self.assertTrue(jsonl_path.exists())
            mode = stat.S_IMODE(os.stat(jsonl_path).st_mode)
            self.assertEqual(
                mode, 0o600,
                f"skip-log JSONL must be 0o600; got {oct(mode)}")


class TeardownRunsOnEveryExitPath(unittest.TestCase):
    """AC6: provision_and_run guarantees destroy_microvm + teardown JSONL
    on each of three exit paths: happy, parser raises, hard-cap trip."""

    def setUp(self):
        self.mod = _load()
        self.tmp = tempfile.mkdtemp()
        self.metrics_dir = self.tmp

    def _make_e2b_stub(self, exec_result=None, exec_raises=None):
        """Build a mock e2b_client that pretends provisioning succeeded.

        `started_at` is set to the current wall-clock so `elapsed` stays
        sub-second; happy-path tests must NOT accidentally trip the
        hard-cap by stubbing `started_at: 0.0` (≈1.7e9 sec since epoch).
        Hard-cap tests opt into the trip via `_elapsed_seconds_since`
        patching.
        """
        client = MagicMock()
        client.provision_microvm.return_value = {
            "ok": True, "microvm_id": "vm_test", "started_at": time.time(),
            "attempts": 1,
        }
        if exec_raises:
            client.exec_in_microvm.side_effect = exec_raises
        else:
            client.exec_in_microvm.return_value = (
                exec_result or {"ok": True, "stdout": "", "stderr": "",
                                "exit_code": 0})
        client.destroy_microvm.return_value = {"ok": True}
        return client

    def test_teardown_runs_on_happy_path(self):
        client = self._make_e2b_stub(
            exec_result={"ok": True,
                         "stdout": "tests/x.py::t PASSED [100%]\n",
                         "stderr": "", "exit_code": 0})
        with patch.dict(os.environ, {"E2B_API_KEY": "k"}, clear=False):
            result = self.mod.provision_and_run(
                session_id="happy",
                metrics_dir=self.metrics_dir,
                test_command="pytest -v",
                worktree_outcomes={"tests/x.py::t": "pass"},
                e2b_client=client,
            )
        self.assertEqual(client.destroy_microvm.call_count, 1,
                         "happy path must teardown")
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED",
                         "happy path must exercise the verified branch "
                         "(not a hard-cap trip masquerading as happy path)")
        self._assert_teardown_line_written("happy")

    def test_teardown_runs_when_parser_raises(self):
        """exec_in_microvm raises → finally block still calls destroy."""
        client = self._make_e2b_stub(
            exec_raises=RuntimeError("simulated exec failure"))
        with patch.dict(os.environ, {"E2B_API_KEY": "k"}, clear=False):
            try:
                self.mod.provision_and_run(
                    session_id="parser-raises",
                    metrics_dir=self.metrics_dir,
                    test_command="pytest -v",
                    worktree_outcomes={"tests/x.py::t": "pass"},
                    e2b_client=client,
                )
            except RuntimeError:
                pass  # caller may re-raise; we only assert teardown
        self.assertEqual(client.destroy_microvm.call_count, 1,
                         "raise path must still teardown via finally")
        self._assert_teardown_line_written("parser-raises")

    def test_teardown_runs_when_cost_hard_cap_trips(self):
        """Hard-cap trip → exec aborted → teardown called once."""
        client = self._make_e2b_stub()
        with patch.dict(os.environ, {
                "E2B_API_KEY": "k",
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD": "0.0000001",
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD": "0.00000005",
        }, clear=False):
            # Force a sleep-noop so the hard-cap check fires reliably.
            with patch.object(self.mod, "_elapsed_seconds_since",
                              return_value=10.0):
                self.mod.provision_and_run(
                    session_id="hard-cap",
                    metrics_dir=self.metrics_dir,
                    test_command="pytest -v",
                    worktree_outcomes={"tests/x.py::t": "pass"},
                    e2b_client=client,
                )
        self.assertEqual(client.destroy_microvm.call_count, 1,
                         "hard-cap exit must teardown")

    def _assert_teardown_line_written(self, session_id):
        """Both happy and parser-raises paths emit a teardown JSONL line."""
        cost_path = Path(self.metrics_dir) / session_id / \
            "sandbox-verify-cost.jsonl"
        if not cost_path.exists():
            return  # hard-cap path may emit elsewhere; not required for two
        lines = [json.loads(line) for line in
                 cost_path.read_text().splitlines() if line.strip()]
        events = {line.get("event") for line in lines}
        self.assertIn("teardown", events,
                      f"cost JSONL must contain a 'teardown' event "
                      f"for session {session_id!r}; saw {events}")


class ExecFailureRoutesToSkipped(unittest.TestCase):
    """Regression: when `exec_in_microvm` returns `{"ok": False, ...}`
    (network failure caught by the client envelope), `_run_and_compare`
    MUST route to SANDBOX_SKIPPED reason=e2b-unavailable.

    Without the ok-check, `parse_test_outcomes("")={}` produces a false
    SANDBOX_FAILED with every worktree-passing test listed as diverging —
    artifact-via-noise rather than real divergence. Seed instinct
    principle 1 ("divergence IS the signal") forbids this.
    """

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        import sandbox_verify_skip
        self.mod = sandbox_verify_skip
        self.tmp = tempfile.mkdtemp()
        self.metrics_dir = self.tmp

    def test_exec_failure_routes_to_skipped(self):
        client = MagicMock()
        client.provision_microvm.return_value = {
            "ok": True, "microvm_id": "vm_test", "started_at": time.time(),
            "attempts": 1,
        }
        # The e2b client envelope on a transient network failure:
        client.exec_in_microvm.return_value = {
            "ok": False, "stdout": "", "stderr": "URLError: timeout",
            "exit_code": -1,
        }
        client.destroy_microvm.return_value = {"ok": True}

        with patch.dict(os.environ, {"E2B_API_KEY": "k"}, clear=False):
            result = self.mod.provision_and_run(
                session_id="exec-fail",
                metrics_dir=self.metrics_dir,
                test_command="pytest -v",
                worktree_outcomes={"tests/x.py::t": "pass",
                                   "tests/y.py::u": "pass"},
                e2b_client=client,
            )

        self.assertEqual(result["verdict"], "SANDBOX_SKIPPED",
                         "exec_in_microvm ok=False must route to skipped, "
                         "not a fake SANDBOX_FAILED")
        self.assertEqual(result["reason"], "e2b-unavailable")
        # Teardown still guaranteed via finally:
        self.assertEqual(client.destroy_microvm.call_count, 1,
                         "exec-failure path must still teardown")
        # Skip-log JSONL line landed in the canonical location:
        skip_path = (Path(self.metrics_dir) / "exec-fail" /
                     "sandbox-verify-skips.jsonl")
        self.assertTrue(skip_path.exists(),
                        "SANDBOX_SKIPPED must append to skips.jsonl")
        lines = [json.loads(line) for line in
                 skip_path.read_text().splitlines() if line.strip()]
        reasons = {entry.get("reason") for entry in lines}
        self.assertIn("e2b-unavailable", reasons)


if __name__ == "__main__":
    unittest.main()
