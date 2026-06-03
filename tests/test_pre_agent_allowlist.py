"""Bash hook + stdin script smoke for pre-agent-allowlist."""
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

# Ensure hook subprocesses can import yaml (pyyaml) and other hook deps.
# The hook's python3 invocation inherits the subprocess env; without
# site-packages in PYTHONPATH it silently fails (|| exit 0 in the hook).
_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _hook_env(extra=None, plugin_data=None):
    """Build a hermetic subprocess env with CLAUDE_PLUGIN_DATA isolation.

    Sets CLAUDE_PLUGIN_DATA + HOME so all runtime-state writes go to tmp_path.
    Sets CLAUDE_PLUGIN_ROOT to repo root so harness_root()/"agents" resolves
    correctly (agent frontmatter lookup for allowlist decisions).
    Ensures PYTHONPATH includes site-packages so hook's python3 can import yaml.
    """
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    env = {**os.environ, "PYTHONPATH": merged_pp,
           "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if plugin_data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        env["HOME"] = str(plugin_data)
    if extra:
        env.update(extra)
    return env


def _run_hook(payload, env=None, plugin_data=None):
    proc_env = _hook_env(extra=env, plugin_data=plugin_data)
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


class _HookTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="allowlist-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _log_path(self, session, filename="tool-allowlist.jsonl"):
        return self.plugin_data / "metrics" / session / filename

    def _run(self, payload, extra_env=None):
        env = extra_env or {}
        return _run_hook(payload, env=env, plugin_data=self.plugin_data)


class HookFastExitsWhenDisabled(_HookTestCase):
    def test_disabled_via_env_skips_all_processing(self):
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            extra_env={"CLAUDE_DISABLE_TOOL_ALLOWLIST": "1"})
        self.assertEqual(result.returncode, 0)
        # No output — fast exit before resolver
        self.assertEqual(result.stdout, "")


class HookLogsAdvisoryWhenSchemaAbsent(_HookTestCase):
    """Path B today — the schema does not expose allowed_tools, so every
    Agent spawn for a known role with a tools list is logged as advisory."""

    def test_logs_schema_absent_when_allowed_tools_missing(self):
        session = f"test-{uuid.uuid4()}"
        log_path = self._log_path(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        self.assertTrue(log_path.exists(), f"expected log at {log_path}")
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "advisory")
        self.assertEqual(entry["agent_role"], "software-engineer")


class HookLogsBlockWithFullDetails(_HookTestCase):
    def test_logs_blocked_and_exits_two(self):
        """Post-flip (Slice A 2026-05-14): action="would_block" → JSONL
        action="blocked" + stderr BLOCKED + exit 2. Pre-flip name kept on
        the class for diff-discoverability; behaviour now asserts enforcement."""
        session = f"test-{uuid.uuid4()}"
        log_path = self._log_path(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Read", "Write", "Edit"]}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 2)
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "blocked")
        self.assertEqual(entry["requested_tools"], ["Read", "Write", "Edit"])
        self.assertIn("Write", entry["offending_tools"])
        self.assertIn("Edit", entry["offending_tools"])
        self.assertEqual(entry["source"], "path-b-advisory")


class HookSanitisesSessionIdAgainstTraversal(_HookTestCase):
    """CRITICAL — a traversal CLAUDE_SESSION_ID must NOT escape metrics dir."""

    def test_traversal_session_id_does_not_escape_metrics_dir(self):
        target = Path("/tmp/sec-poc-test-allowlist/PWNED")
        if target.exists():
            target.unlink()
        if target.parent.exists():
            try:
                target.parent.rmdir()
            except OSError:
                pass
        try:
            result = self._run(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                extra_env={"CLAUDE_SESSION_ID": "../../../../tmp/sec-poc-test-allowlist/PWNED"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(target.exists(),
                             "traversal escaped: file at /tmp/sec-poc...")
        finally:
            if target.exists():
                target.unlink()
            if target.parent.exists():
                try:
                    target.parent.rmdir()
                except OSError:
                    pass


class HookCapsAgentRoleLength(_HookTestCase):
    """A 1MB subagent_type must NOT produce an unbounded log line."""

    def test_million_char_subagent_type_produces_capped_log_line(self):
        session = f"test-cap-{uuid.uuid4()}"
        log_path = self._log_path(session)
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "A" * 1_000_000}}
        result = self._run(payload, extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        # Traversal validation will reject the giant string (uppercase A
        # fails the kebab regex), so the resolver returns SKIP — no log.
        # If a log IS produced, it MUST be capped.
        if log_path.exists():
            line = log_path.read_text().strip().splitlines()[-1]
            self.assertLessEqual(len(line), 1024)
            self.assertLessEqual(len(json.loads(line)["agent_role"]), 64)

class HookRespectsHookProfileGating(_HookTestCase):
    def test_minimal_profile_disables_hook(self):
        session = f"test-prof-{uuid.uuid4()}"
        log_path = self._log_path(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            extra_env={"CLAUDE_SESSION_ID": session,
                       "CLAUDE_HOOK_PROFILE": "minimal"})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(log_path.exists(),
                         "minimal profile should suppress allowlist log")


class HookWiresFrontmatterToolsThroughPipeline(_HookTestCase):
    """HIGH-2: resolver knows the frontmatter tools but the previous pipeline
    never forwarded them, so the documented `frontmatter_tools` field never
    appeared on `would_block` entries. Verify end-to-end flow now writes it."""

    def test_would_block_entry_includes_frontmatter_tools(self):
        session = f"test-fm-{uuid.uuid4()}"
        log_path = self._log_path(session)
        self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Read", "Write", "Edit"]}},
            extra_env={"CLAUDE_SESSION_ID": session})
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "blocked")
        self.assertIn("frontmatter_tools", entry)
        self.assertIsInstance(entry["frontmatter_tools"], list)
        self.assertGreater(len(entry["frontmatter_tools"]), 0)

    def test_advisory_entry_omits_frontmatter_tools(self):
        session = f"test-fm-adv-{uuid.uuid4()}"
        log_path = self._log_path(session)
        self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        self.assertEqual(entry["action"], "advisory")
        self.assertNotIn("frontmatter_tools", entry)


class HookEmitsValidJsonUnderLargePayload(_HookTestCase):
    """HIGH-1: previous code truncated json.dumps at 1024 chars producing
    malformed JSON that crashed json.loads(). Field-level caps now keep
    the line bounded AND syntactically valid."""

    def test_large_offending_and_requested_tools_remain_valid_json(self):
        session = f"test-valid-{uuid.uuid4()}"
        log_path = self._log_path(session)
        # 50 long tool strings would have spilled past 1024 in the old code
        big_tools = ["LongToolName_" + ("x" * 80) for _ in range(50)]
        self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": big_tools}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertTrue(log_path.exists())
        line = log_path.read_text().strip().splitlines()[-1]
        entry = json.loads(line)  # MUST NOT raise
        # Field caps enforced at 20 entries
        self.assertLessEqual(len(entry["requested_tools"]), 20)
        self.assertLessEqual(len(entry.get("offending_tools", [])), 20)


class HookSkipsSilentlyOnNonAgent(_HookTestCase):
    def test_non_agent_tool_does_not_create_log_file(self):
        session = f"test-{uuid.uuid4()}"
        log_path = self._log_path(session)
        result = self._run(
            {"tool_name": "Bash", "tool_input": {}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(log_path.exists(),
                         "non-Agent tool should not create allowlist log")
