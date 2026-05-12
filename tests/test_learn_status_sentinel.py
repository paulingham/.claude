"""B8.1 — learn-status sentinel lifecycle.

Asserts the lifecycle of the new ``last_learn_started`` field on
``learning/{project-hash}/.learn-state.json``:

- mark_started writes ``last_learn_started`` (and creates the state file
  if absent) without touching ``last_learn_run`` or other counters
- mark_completed writes ``last_learn_run`` >= the started timestamp
- The pre-flight predicate returns ``"in-flight"`` while
  ``last_learn_started > last_learn_run`` (or ``last_learn_run is null``)
  and ``"idle"`` once ``last_learn_run >= last_learn_started``

Also asserts the AC1/AC2/AC3 documentation contracts via structural
grep — markdown is the deliverable for those ACs.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learn_status  # noqa: E402  (path inserted above)


def _read(path):
    return json.loads(Path(path).read_text())


class MarkStartedWritesSentinel(unittest.TestCase):
    def test_creates_state_file_with_started_when_absent(self):
        with _tmp() as state:
            learn_status.mark_started(state, "2026-05-04T10:00:00Z")
            data = _read(state)
            self.assertEqual(data["last_learn_started"], "2026-05-04T10:00:00Z")
            self.assertIsNone(data["last_learn_run"])

    def test_preserves_existing_counters(self):
        with _tmp() as state:
            Path(state).write_text(json.dumps({
                "last_learn_run": "2026-05-01T00:00:00Z",
                "pipelines_since_learn": 2,
                "observations_since_learn": 5,
                "last_fired_pipeline_id": "task-x",
                "last_observation_offset": 1024,
            }))
            learn_status.mark_started(state, "2026-05-04T10:00:00Z")
            data = _read(state)
            self.assertEqual(data["last_learn_started"], "2026-05-04T10:00:00Z")
            self.assertEqual(data["pipelines_since_learn"], 2)
            self.assertEqual(data["observations_since_learn"], 5)
            self.assertEqual(data["last_fired_pipeline_id"], "task-x")
            self.assertEqual(data["last_observation_offset"], 1024)
            self.assertEqual(data["last_learn_run"], "2026-05-01T00:00:00Z")


class MarkCompletedAdvancesRun(unittest.TestCase):
    def test_run_after_started_is_idle(self):
        with _tmp() as state:
            learn_status.mark_started(state, "2026-05-04T10:00:00Z")
            learn_status.mark_completed(state, "2026-05-04T10:05:00Z")
            data = _read(state)
            self.assertGreaterEqual(data["last_learn_run"], data["last_learn_started"])

    def test_completed_does_not_clear_started(self):
        with _tmp() as state:
            learn_status.mark_started(state, "2026-05-04T10:00:00Z")
            learn_status.mark_completed(state, "2026-05-04T10:05:00Z")
            data = _read(state)
            self.assertEqual(data["last_learn_started"], "2026-05-04T10:00:00Z")


class StatusPredicate(unittest.TestCase):
    def test_in_flight_when_started_after_run(self):
        state = {"last_learn_started": "2026-05-04T10:00:00Z",
                 "last_learn_run": "2026-05-04T09:00:00Z"}
        self.assertTrue(learn_status.is_in_flight(state))
        self.assertEqual(learn_status.status_for(state), "in-flight")

    def test_in_flight_when_run_is_null(self):
        state = {"last_learn_started": "2026-05-04T10:00:00Z",
                 "last_learn_run": None}
        self.assertTrue(learn_status.is_in_flight(state))
        self.assertEqual(learn_status.status_for(state), "in-flight")

    def test_idle_when_run_after_or_equal_started(self):
        state = {"last_learn_started": "2026-05-04T10:00:00Z",
                 "last_learn_run": "2026-05-04T10:05:00Z"}
        self.assertFalse(learn_status.is_in_flight(state))
        self.assertEqual(learn_status.status_for(state), "idle")

    def test_idle_when_started_is_null(self):
        # Never started ⇒ idle (no /learn invocation in flight).
        state = {"last_learn_started": None, "last_learn_run": None}
        self.assertFalse(learn_status.is_in_flight(state))
        self.assertEqual(learn_status.status_for(state), "idle")

    def test_status_from_path_round_trip(self):
        with _tmp() as state:
            learn_status.mark_started(state, "2026-05-04T10:00:00Z")
            self.assertEqual(learn_status.status_for_path(state), "in-flight")
            learn_status.mark_completed(state, "2026-05-04T10:05:00Z")
            self.assertEqual(learn_status.status_for_path(state), "idle")


class HelperUsesJsonDumpsNotPrintf(unittest.TestCase):
    """AC5 instinct: dynamic JSONL emission must use json.dumps, not bash printf."""

    def test_no_printf_format_strings_in_helper(self):
        body = (REPO_ROOT / "hooks" / "_lib" / "learn_status.py").read_text()
        self.assertNotIn('printf "', body, "do not emit JSON via shell printf")
        self.assertIn("json.dumps", body, "must use json.dumps for serialisation")


class DocsRecordBackgroundSpawnContract(unittest.TestCase):
    """AC1: § 6b in reflection-protocol.md must specify background-spawn."""

    def test_reflection_protocol_specifies_run_in_background(self):
        path = REPO_ROOT / "protocols" / "reflection-protocol.md"
        body = path.read_text()
        # AC1: literal phrase OR substantive equivalent.
        self.assertIn("Pipeline must NOT block on /learn completion", body)
        # AC1: background-spawn pattern named.
        self.assertIn("run_in_background: true", body)


class DocsRecordPreflightLearnStatusCheck(unittest.TestCase):
    """AC2: orchestrator pre-flight gains a learn-status check."""

    def test_preflight_section_describes_learn_status(self):
        path = REPO_ROOT / "orchestrator" / "pipeline-orchestration.md"
        body = path.read_text()
        self.assertIn("learn-status check", body)
        # AC2: predicate named explicitly.
        self.assertIn("last_learn_started", body)
        self.assertIn("last_learn_run", body)
        # AC2: queue behaviour documented.
        self.assertIn("defer", body.lower())


class DocsRecordSkillStartedWriter(unittest.TestCase):
    """AC3: skills/learn/SKILL.md writes last_learn_started early."""

    def test_skill_writes_last_learn_started(self):
        body = (REPO_ROOT / "skills" / "learn" / "SKILL.md").read_text()
        self.assertIn("last_learn_started", body)


# --- helpers ---------------------------------------------------------------


@contextlib.contextmanager
def _tmp():
    with tempfile.TemporaryDirectory() as d:
        yield str(Path(d) / ".learn-state.json")


if __name__ == "__main__":
    unittest.main()
