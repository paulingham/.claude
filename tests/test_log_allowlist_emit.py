"""Direct unit tests for log_allowlist_emit (entry construction + main I/O).

Bash-hook-level integration coverage lives in test_pre_agent_allowlist.py;
this module exercises the Python module in isolation so failures point at
the emit logic rather than the wrapper plumbing.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EMIT_PATH = REPO_ROOT / "hooks" / "_lib" / "log_allowlist_emit.py"

# Module name has a hyphen-equivalent in path; load via spec for stability
_spec = importlib.util.spec_from_file_location("log_allowlist_emit", EMIT_PATH)
emit = importlib.util.module_from_spec(_spec)
sys.modules["log_allowlist_emit"] = emit
_spec.loader.exec_module(emit)


def _invoke_main(timestamp, payload, resolved, out_path, frontmatter=None):
    argv = [
        "log_allowlist_emit.py",
        timestamp,
        json.dumps(payload),
        json.dumps(resolved),
        str(out_path),
    ]
    if frontmatter is not None:
        argv.append(json.dumps(frontmatter) if frontmatter != "null" else "null")
    saved = sys.argv
    try:
        sys.argv = argv
        emit.main()
    finally:
        sys.argv = saved


class EntryFieldCaps(unittest.TestCase):
    """HIGH-1: cap fields BEFORE serialisation so output is bounded AND valid."""

    def test_requested_tools_capped_at_20_entries(self):
        big = [f"Tool{i}" for i in range(50)]
        entry = emit._entry(
            "2026-04-26T00:00:00Z",
            {"tool_input": {"subagent_type": "x", "allowed_tools": big}},
            {"action": "would_block", "offending_tools": []})
        self.assertEqual(len(entry["requested_tools"]), 20)
        self.assertEqual(entry["requested_tools"][0], "Tool0")

    def test_offending_tools_capped_at_20_entries(self):
        big = [f"Bad{i}" for i in range(50)]
        entry = emit._entry(
            "2026-04-26T00:00:00Z",
            {"tool_input": {"subagent_type": "x"}},
            {"action": "would_block", "offending_tools": big})
        self.assertEqual(len(entry["offending_tools"]), 20)


class MainProducesValidJsonOnLargePayload(unittest.TestCase):
    """HIGH-1 regression — written line MUST round-trip through json.loads."""

    def test_main_writes_parseable_json_with_huge_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "log.jsonl"
            big_tools = ["LongName_" + ("z" * 200) for _ in range(40)]
            _invoke_main(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": big_tools}},
                {"action": "would_block", "offending_tools": big_tools},
                out)
            line = out.read_text().strip()
            entry = json.loads(line)  # must not raise
            self.assertEqual(len(entry["requested_tools"]), 20)
            self.assertEqual(len(entry["offending_tools"]), 20)


class MainAcceptsFrontmatterPositionalArg(unittest.TestCase):
    """HIGH-2: frontmatter_tools wired through pipeline as 5th argv."""

    def test_would_block_with_frontmatter_emits_field(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "log.jsonl"
            _invoke_main(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write"]}},
                {"action": "would_block", "offending_tools": ["Write"]},
                out,
                frontmatter=["Read", "Grep", "Glob"])
            entry = json.loads(out.read_text().strip())
            self.assertEqual(entry["frontmatter_tools"], ["Read", "Grep", "Glob"])

    def test_would_block_with_null_frontmatter_omits_field(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "log.jsonl"
            _invoke_main(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Read", "Write"]}},
                {"action": "would_block", "offending_tools": ["Write"]},
                out,
                frontmatter="null")
            entry = json.loads(out.read_text().strip())
            self.assertNotIn("frontmatter_tools", entry)

    def test_advisory_action_never_attaches_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "log.jsonl"
            _invoke_main(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "code-reviewer"}},
                {"action": "advisory", "offending_tools": []},
                out,
                frontmatter=["Read", "Grep"])
            entry = json.loads(out.read_text().strip())
            self.assertNotIn("frontmatter_tools", entry)

    def test_frontmatter_tools_capped_at_20_entries(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "log.jsonl"
            _invoke_main(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "code-reviewer",
                                "allowed_tools": ["Write"]}},
                {"action": "would_block", "offending_tools": ["Write"]},
                out,
                frontmatter=[f"T{i}" for i in range(50)])
            entry = json.loads(out.read_text().strip())
            self.assertEqual(len(entry["frontmatter_tools"]), 20)


class SessionIdSanitisation(unittest.TestCase):
    """MEDIUM: log path and json session_id field MUST agree."""

    def test_sanitize_replaces_disallowed_chars(self):
        self.assertEqual(emit._sanitize_session("foo/bar"), "foo_bar")

    def test_sanitize_falls_back_when_all_chars_stripped(self):
        result = emit._sanitize_session("////")
        self.assertTrue(result.startswith("local-"))

    def test_sanitize_caps_at_64_chars(self):
        result = emit._sanitize_session("a" * 200)
        self.assertEqual(len(result), 64)

    def test_entry_session_id_uses_sanitised_value(self):
        prior = os.environ.get("CLAUDE_SESSION_ID")
        os.environ["CLAUDE_SESSION_ID"] = "foo/bar"
        try:
            entry = emit._entry(
                "2026-04-26T00:00:00Z",
                {"tool_input": {"subagent_type": "x"}},
                {"action": "advisory", "offending_tools": []})
            self.assertEqual(entry["session_id"], "foo_bar")
        finally:
            if prior is None:
                del os.environ["CLAUDE_SESSION_ID"]
            else:
                os.environ["CLAUDE_SESSION_ID"] = prior


if __name__ == "__main__":
    unittest.main()
