"""Slice A — pre-agent-allowlist.sh promoted from log-only to exit-2 enforcement.

Tests the flip behaviour:
  - $RESOLVED.action == "would_block" → stderr "BLOCKED:" + JSONL "blocked" + exit 2
  - CLAUDE_DISABLE_TOOL_ALLOWLIST=1 bypasses block (env-hatch reversibility)
  - $RESOLVED.action in {ok, advisory} → log-and-exit-0 happy path preserved
  - resolver crash → fail-open exit 0 (preserve existing behaviour)
"""
import json
import os
import subprocess
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-allowlist.sh"


def _run_hook(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _log_path(session):
    return Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


class WouldBlockExitsTwoWithStderr(unittest.TestCase):
    """AC-A1: when the resolver classifies action=would_block, the hook MUST
    exit 2 and emit a stderr line starting `BLOCKED:` with the offending
    tool list. Spawn is denied — no longer log-only."""

    def test_would_block_exits_2_with_stderr(self):
        session = f"test-flip-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write", "Edit"]}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 2,
                             f"expected exit 2; got {result.returncode}; "
                             f"stderr={result.stderr!r}")
            self.assertIn("BLOCKED:", result.stderr)
            # offending tools must surface in the stderr line for operator triage
            self.assertTrue("Write" in result.stderr or "Edit" in result.stderr,
                            f"stderr lacks offending tool: {result.stderr!r}")
        finally:
            _cleanup(log_path)


class WouldBlockWritesJsonlBeforeExit(unittest.TestCase):
    """AC-A2: the JSONL log line MUST be written BEFORE exit-2, with
    action="blocked" (NOT "would_block" — the old advisory token).
    This is the audit trail for the now-enforcing decision."""

    def test_would_block_writes_jsonl_before_exit(self):
        session = f"test-blockjsonl-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Write"]}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 2)
            self.assertTrue(log_path.exists(),
                            f"expected JSONL at {log_path} before exit-2")
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "blocked",
                             f"expected action=blocked; got {entry!r}")
            self.assertEqual(entry["agent_role"], "code-reviewer")
        finally:
            _cleanup(log_path)


class DisableEnvVarBypassesBlock(unittest.TestCase):
    """AC-A3: CLAUDE_DISABLE_TOOL_ALLOWLIST=1 short-circuits the hook to
    exit 0 BEFORE the resolver runs — the reversibility escape hatch.
    No JSONL line is appended (the hook never reaches the log path)."""

    def test_disable_env_var_bypasses_block(self):
        session = f"test-disable-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Write", "Edit"]}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_TOOL_ALLOWLIST": "1"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "disable env-var should suppress all logging")
        finally:
            _cleanup(log_path)


class OkAndAdvisoryActionsLogAndExitZero(unittest.TestCase):
    """AC-A4: when resolver returns action in {ok, advisory}, hook still
    logs (audit trail) and exits 0 — the happy path is preserved."""

    def test_advisory_logs_and_exits_0(self):
        session = f"test-advisory-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            # software-engineer with no allowed_tools → schema-absent → advisory
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists())
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "advisory")
        finally:
            _cleanup(log_path)


class ResolverCrashFailsOpen(unittest.TestCase):
    """AC-A5: resolver crash → hook exits 0 (fail-open). A broken resolver
    must not deny every spawn — better to log-only than brick the harness."""

    def test_resolver_crash_fails_open(self):
        # Inject malformed JSON: payload that the resolver's json.loads can
        # parse (empty dict) but with no subagent_type — resolver returns SKIP
        # and the hook should exit 0 silently.
        session = f"test-crash-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent", "tool_input": {}},
                env={"CLAUDE_SESSION_ID": session})
            # SKIP path → exit 0, no stderr noise
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
        finally:
            _cleanup(log_path)


if __name__ == "__main__":
    unittest.main()
