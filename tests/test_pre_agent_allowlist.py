"""Bash hook + stdin script smoke for pre-agent-allowlist."""
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


class HookFastExitsWhenDisabled(unittest.TestCase):
    def test_disabled_via_env_skips_all_processing(self):
        result = _run_hook(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer"}},
            env={"CLAUDE_DISABLE_TOOL_ALLOWLIST": "1"})
        self.assertEqual(result.returncode, 0)
        # No output — fast exit before resolver
        self.assertEqual(result.stdout, "")


class HookLogsAdvisoryWhenSchemaAbsent(unittest.TestCase):
    """Path B today — the schema does not expose allowed_tools, so every
    Agent spawn for a known role with a tools list is logged as advisory."""

    def test_logs_schema_absent_when_allowed_tools_missing(self):
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(), f"expected log at {log_path}")
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "advisory")
            self.assertEqual(entry["agent_role"], "software-engineer")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookLogsBlockWithFullDetails(unittest.TestCase):
    def test_logs_would_block_and_exits_zero_today(self):
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write", "Edit"]}},
                env={"CLAUDE_SESSION_ID": session})
            # Path B today — exit 0 even on would_block
            self.assertEqual(result.returncode, 0)
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "would_block")
            self.assertEqual(entry["requested_tools"], ["Read", "Write", "Edit"])
            # code-reviewer's frontmatter currently lacks Bash/Write/Edit
            self.assertIn("Write", entry["offending_tools"])
            self.assertIn("Edit", entry["offending_tools"])
            self.assertEqual(entry["source"], "path-b-advisory")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookSanitisesSessionIdAgainstTraversal(unittest.TestCase):
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
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": "../../../../tmp/sec-poc-test-allowlist/PWNED"})
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


class HookCapsAgentRoleLength(unittest.TestCase):
    """A 1MB subagent_type must NOT produce an unbounded log line."""

    def test_million_char_subagent_type_produces_capped_log_line(self):
        session = f"test-cap-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type": "A" * 1_000_000}}
            result = _run_hook(payload, env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            # Traversal validation will reject the giant string (uppercase A
            # fails the kebab regex), so the resolver returns SKIP — no log.
            # If a log IS produced, it MUST be capped.
            if log_path.exists():
                line = log_path.read_text().strip().splitlines()[-1]
                self.assertLessEqual(len(line), 1024)
                self.assertLessEqual(len(json.loads(line)["agent_role"]), 64)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()

    def test_full_log_line_capped_at_1024_bytes(self):
        # Use valid software-engineer with a giant requested allowed_tools list
        # that would otherwise blow past 1024 bytes. The cap should truncate.
        session = f"test-line-cap-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            big_tools = ["X" * 100 for _ in range(50)]
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer",
                                "allowed_tools": big_tools}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertTrue(log_path.exists())
            line = log_path.read_text().strip().splitlines()[-1]
            # Allow newline; the cap is on JSON content
            self.assertLessEqual(len(line.rstrip("\n")), 1024)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookRespectsHookProfileGating(unittest.TestCase):
    def test_minimal_profile_disables_hook(self):
        session = f"test-prof-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_HOOK_PROFILE": "minimal"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "minimal profile should suppress allowlist log")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookSkipsSilentlyOnNonAgent(unittest.TestCase):
    def test_non_agent_tool_does_not_create_log_file(self):
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Bash", "tool_input": {}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "non-Agent tool should not create allowlist log")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()
