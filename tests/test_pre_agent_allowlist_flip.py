"""Slice A — pre-agent-allowlist.sh promoted from log-only to exit-2 enforcement.

Tests the flip behaviour:
  - $RESOLVED.action == "would_block" → stderr "BLOCKED:" + JSONL "blocked" + exit 2
  - CLAUDE_DISABLE_TOOL_ALLOWLIST=1 bypasses block (env-hatch reversibility)
  - $RESOLVED.action in {ok, advisory} → log-and-exit-0 happy path preserved
  - resolver crash → fail-open exit 0 (preserve existing behaviour)
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
HOOK = REPO_ROOT / "hooks" / "pre-agent-allowlist.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(payload, env=None, plugin_data=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env = {**os.environ, "PYTHONPATH": merged_pp,
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if plugin_data is not None:
        proc_env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        proc_env["HOME"] = str(plugin_data)
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _log_path(session, base):
    return base / "metrics" / session / "tool-allowlist.jsonl"


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


class _FlipTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="flip-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _log(self, session):
        return _log_path(session, base=self.plugin_data)

    def _run(self, payload, extra_env=None):
        return _run_hook(payload, env=extra_env, plugin_data=self.plugin_data)


class WouldBlockExitsTwoWithStderr(_FlipTestCase):
    """AC-A1: when the resolver classifies action=would_block, the hook MUST
    exit 2 and emit a stderr line starting `BLOCKED:` with the offending
    tool list. Spawn is denied — no longer log-only."""

    def test_would_block_exits_2_with_stderr(self):
        session = f"test-flip-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Read", "Write", "Edit"]}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 2,
                         f"expected exit 2; got {result.returncode}; "
                         f"stderr={result.stderr!r}")
        self.assertIn("BLOCKED:", result.stderr)
        self.assertTrue("Write" in result.stderr or "Edit" in result.stderr,
                        f"stderr lacks offending tool: {result.stderr!r}")


class WouldBlockWritesJsonlBeforeExit(_FlipTestCase):
    """AC-A2: the JSONL log line MUST be written BEFORE exit-2, with
    action="blocked" (NOT "would_block" — the old advisory token)."""

    def test_would_block_writes_jsonl_before_exit(self):
        session = f"test-blockjsonl-{uuid.uuid4()}"
        log_path = self._log(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Write"]}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 2)
        self.assertTrue(log_path.exists(),
                        f"expected JSONL at {log_path} before exit-2")
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "blocked",
                         f"expected action=blocked; got {entry!r}")
        self.assertEqual(entry["agent_role"], "code-reviewer")


class DisableEnvVarBypassesBlock(_FlipTestCase):
    """AC-A3: CLAUDE_DISABLE_TOOL_ALLOWLIST=1 short-circuits the hook."""

    def test_disable_env_var_bypasses_block(self):
        session = f"test-disable-{uuid.uuid4()}"
        log_path = self._log(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Write", "Edit"]}},
            extra_env={"CLAUDE_SESSION_ID": session,
                       "CLAUDE_DISABLE_TOOL_ALLOWLIST": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(log_path.exists(),
                         "disable env-var should suppress all logging")


class OkAndAdvisoryActionsLogAndExitZero(_FlipTestCase):
    """AC-A4: action in {ok, advisory} → log and exit 0."""

    def test_advisory_logs_and_exits_0(self):
        session = f"test-advisory-{uuid.uuid4()}"
        log_path = self._log(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        self.assertTrue(log_path.exists())
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "advisory")


class ResolverCrashFailsOpen(_FlipTestCase):
    """AC-A5: resolver crash → hook exits 0 (fail-open)."""

    def test_resolver_crash_fails_open(self):
        session = f"test-crash-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent", "tool_input": {}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
