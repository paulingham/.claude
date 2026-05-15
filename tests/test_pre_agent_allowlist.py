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
    def test_logs_blocked_and_exits_two(self):
        """Post-flip (Slice A 2026-05-14): action="would_block" → JSONL
        action="blocked" + stderr BLOCKED + exit 2. Pre-flip name kept on
        the class for diff-discoverability; behaviour now asserts enforcement."""
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write", "Edit"]}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 2)
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "blocked")
            self.assertEqual(entry["requested_tools"], ["Read", "Write", "Edit"])
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


class HookWiresFrontmatterToolsThroughPipeline(unittest.TestCase):
    """HIGH-2: resolver knows the frontmatter tools but the previous pipeline
    never forwarded them, so the documented `frontmatter_tools` field never
    appeared on `would_block` entries. Verify end-to-end flow now writes it."""

    def test_would_block_entry_includes_frontmatter_tools(self):
        session = f"test-fm-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write", "Edit"]}},
                env={"CLAUDE_SESSION_ID": session})
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            # Post-flip: action is "blocked" (audit trail for denied spawn).
            # Frontmatter attachment in log_allowlist_entry.attach_frontmatter
            # keys on resolved.action == "would_block" — the resolver still
            # emits would_block; the hook rewrites .action to "blocked" only
            # for the entry passed to log-allowlist.sh, but attach_frontmatter
            # reads the rewritten resolved, so the contract is preserved
            # only if we keep the original action visible. Assert the new
            # contract: action=blocked AND frontmatter_tools present.
            self.assertEqual(entry["action"], "blocked")
            self.assertIn("frontmatter_tools", entry)
            # code-reviewer's actual frontmatter tool list — bound shape, not exact
            self.assertIsInstance(entry["frontmatter_tools"], list)
            self.assertGreater(len(entry["frontmatter_tools"]), 0)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()

    def test_advisory_entry_omits_frontmatter_tools(self):
        session = f"test-fm-adv-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer"}},
                env={"CLAUDE_SESSION_ID": session})
            entry = json.loads(log_path.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["action"], "advisory")
            self.assertNotIn("frontmatter_tools", entry)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookEmitsValidJsonUnderLargePayload(unittest.TestCase):
    """HIGH-1: previous code truncated json.dumps at 1024 chars producing
    malformed JSON that crashed json.loads(). Field-level caps now keep
    the line bounded AND syntactically valid."""

    def test_large_offending_and_requested_tools_remain_valid_json(self):
        session = f"test-valid-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "tool-allowlist.jsonl"
        try:
            # 50 long tool strings would have spilled past 1024 in the old code
            big_tools = ["LongToolName_" + ("x" * 80) for _ in range(50)]
            _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": big_tools}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertTrue(log_path.exists())
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)  # MUST NOT raise
            # Field caps enforced at 20 entries
            self.assertLessEqual(len(entry["requested_tools"]), 20)
            self.assertLessEqual(len(entry.get("offending_tools", [])), 20)
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
