"""Slice A: hooks/quality-gate.sh — fail-loud advisory when CLAUDE_PIPELINE_TASK_ID is empty.

Background: prior to this fix `quality-gate.sh:37` silently resolved
`TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-unknown}"`, which caused concurrent
pipelines to collide on `pipeline-state/unknown/verification-evidence.json`
and corrupt each other's freshness evidence (incident:
`promote-advisory-hooks-enforcement` Ship gate blocked by stale stub from
`model-demotion-pass-2026-05-integration` pipeline).

This slice ships LOG-ONLY initial: emit a stderr message + JSONL advisory
event (source=would-block-task-id) but do NOT block (exit 0). Promotion to
`exit 2` is gated on 14d/50-pipeline soak per the plan.

ACs:
- A1: empty task-id + `gh pr create` → stderr advisory + JSONL line; exit 0
- A2: stderr advisory names env var, root cause, and three fix options
  (set var, /pipeline Step 2c, manual stub refresh recipe)
- A3: task-id set + checks pass → unchanged behaviour (no advisory)
- A4: non-`gh pr create` Bash → unaffected (line-22 short-circuit holds)
"""
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "quality-gate.sh"


def _events_path(session):
    return Path.home() / ".claude" / "metrics" / session / "quality-gate-events.jsonl"


def _cleanup(session):
    p = _events_path(session)
    if p.exists():
        p.unlink()
    if p.parent.exists():
        try:
            p.parent.rmdir()
        except OSError:
            pass


def _run_hook(command, env_overrides=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**os.environ, **(env_overrides or {})}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _read_last_event(session):
    p = _events_path(session)
    if not p.exists():
        return None
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def _read_events(session):
    """All events from the session's JSONL log, oldest first."""
    p = _events_path(session)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _find_event_by_source(session, source):
    for evt in _read_events(session):
        if evt.get("source") == source:
            return evt
    return None


class EmptyTaskIdEmitsAdvisory(unittest.TestCase):
    """A1: empty task-id on `gh pr create` → advisory stderr + JSONL line."""

    def test_empty_task_id_pr_create_emits_advisory(self):
        session = f"test-a1-{uuid.uuid4().hex[:8]}"
        try:
            # Force the freshness check and other checks to short-circuit by
            # running from /tmp where there is no project context. The advisory
            # branch fires BEFORE the check loop, so this is fine.
            r = _run_hook(
                "gh pr create --title x --body y",
                env_overrides={
                    "CLAUDE_PIPELINE_TASK_ID": "",
                    "CLAUDE_SESSION_ID": session,
                },
            )
            # Log-only initial — must not block.
            self.assertEqual(
                r.returncode, 0,
                f"log-only soak: expected exit 0, got {r.returncode}; "
                f"stderr={r.stderr}",
            )
            # Stderr must carry the advisory text.
            self.assertIn("CLAUDE_PIPELINE_TASK_ID", r.stderr)
            # JSONL line with source=would-block-task-id must appear
            # somewhere in the event stream (later events from the
            # check loop may also be present).
            evt = _find_event_by_source(session, "would-block-task-id")
            self.assertIsNotNone(
                evt, f"expected source=would-block-task-id event under "
                f"{_events_path(session)}; events={_read_events(session)}; "
                f"stderr={r.stderr}",
            )
        finally:
            _cleanup(session)


class AdvisoryMessageIsActionable(unittest.TestCase):
    """A2: advisory body names env var, root cause, and three fix options."""

    REQUIRED_LITERALS = (
        "CLAUDE_PIPELINE_TASK_ID",
        "pipeline-state/unknown",
        "/pipeline",
        # Fix-option 3: in-place recovery recipe (per product-reviewer round 1)
        "verification-evidence.json",
    )

    def test_advisory_message_is_actionable(self):
        session = f"test-a2-{uuid.uuid4().hex[:8]}"
        try:
            r = _run_hook(
                "gh pr create --title x --body y",
                env_overrides={
                    "CLAUDE_PIPELINE_TASK_ID": "",
                    "CLAUDE_SESSION_ID": session,
                },
            )
            for literal in self.REQUIRED_LITERALS:
                self.assertIn(
                    literal, r.stderr,
                    f"advisory stderr missing required literal {literal!r}; "
                    f"got: {r.stderr}",
                )
        finally:
            _cleanup(session)


class SetTaskIdPreservesBehaviour(unittest.TestCase):
    """A3: task-id set → no advisory event, no advisory stderr."""

    def test_set_task_id_does_not_emit_advisory(self):
        session = f"test-a3-{uuid.uuid4().hex[:8]}"
        try:
            r = _run_hook(
                "gh pr create --title x --body y",
                env_overrides={
                    "CLAUDE_PIPELINE_TASK_ID": "real-task-id",
                    "CLAUDE_SESSION_ID": session,
                },
            )
            # Quality-gate checks may fail (no project context) but the advisory
            # branch specifically must NOT fire — no event with that source
            # may appear anywhere in the stream.
            self.assertIsNone(
                _find_event_by_source(session, "would-block-task-id"),
                "task-id set but advisory still fired",
            )
            # And no advisory text on stderr.
            self.assertNotIn(
                "would-block-task-id", r.stderr,
                "task-id set but advisory text still rendered",
            )
        finally:
            _cleanup(session)


class NonPrCreateBashUnaffected(unittest.TestCase):
    """A4: non-`gh pr create` Bash → line-22 short-circuit returns exit 0
    with no advisory regardless of task-id."""

    def test_non_pr_create_bash_no_advisory(self):
        session = f"test-a4-{uuid.uuid4().hex[:8]}"
        try:
            r = _run_hook(
                "ls /tmp",
                env_overrides={
                    "CLAUDE_PIPELINE_TASK_ID": "",
                    "CLAUDE_SESSION_ID": session,
                },
            )
            self.assertEqual(r.returncode, 0)
            self.assertFalse(
                _events_path(session).exists(),
                "non-pr-create Bash must not emit any JSONL event",
            )
            self.assertNotIn("CLAUDE_PIPELINE_TASK_ID", r.stderr)
        finally:
            _cleanup(session)


if __name__ == "__main__":
    unittest.main()
