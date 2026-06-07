"""Tests for JSONL record schema — AC12-AC16.

Session from env, record fields, 0o600 file mode, three-tier path cascade,
goal hash stability.
"""
import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)

_REPO_ROOT = Path(__file__).resolve().parents[1]


class TestSessionFromEnv(unittest.TestCase):
    """AC12: session uses CLAUDE_SESSION_ID env var with PID fallback."""

    def test_session_uses_CLAUDE_SESSION_ID_env_var(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild the service\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-abc"}, clear=False):
            record = build_record(payload, [])
        self.assertEqual(record["session"], "test-session-abc")

    def test_session_uses_pid_fallback_when_no_env_var(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild\n",
            }
        }
        env_without_session = {k: v for k, v in os.environ.items()
                               if k != "CLAUDE_SESSION_ID"}
        with patch.dict(os.environ, env_without_session, clear=True):
            record = build_record(payload, [])
        # Should have a session value (PID-based fallback)
        self.assertIsNotNone(record.get("session"))
        self.assertNotEqual(record["session"], "")

    def test_session_sanitized_against_path_traversal(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild\n",
            }
        }
        # Session ID with path traversal characters
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "../../etc/passwd"}, clear=False):
            record = build_record(payload, [])
        # Must not contain path traversal characters
        self.assertNotIn("..", record["session"])
        self.assertNotIn("/", record["session"])
        # Should be sanitized to underscores
        self.assertRegex(record["session"], r"^[A-Za-z0-9_-]+$")


class TestRecordSchema(unittest.TestCase):
    """AC13: record has all required fields, block_type enum valid, tokens=chars/4."""

    VALID_BLOCK_TYPES = {"scratchpad", "protocol", "session_memory", "role_doc",
                         "instincts", "unknown"}

    def _make_record(self):
        from swe_pruner import build_record, segment_content_blocks, propose_drops, extract_goal_keywords
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild the authentication service\n",
            }
        }
        prompt = payload["tool_input"]["prompt"]
        blocks = segment_content_blocks(prompt)
        keywords = extract_goal_keywords("software-engineer", prompt)
        proposals = [(b, propose_drops(b, keywords)) for b in blocks]
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session"}, clear=False):
            return build_record(payload, proposals)

    def test_record_has_timestamp(self):
        record = self._make_record()
        self.assertIn("timestamp", record)

    def test_record_has_session(self):
        record = self._make_record()
        self.assertIn("session", record)

    def test_record_has_agent_role(self):
        record = self._make_record()
        self.assertIn("agent_role", record)
        self.assertEqual(record["agent_role"], "software-engineer")

    def test_record_has_goal_hash(self):
        record = self._make_record()
        self.assertIn("goal_hash", record)

    def test_record_has_keyword_count(self):
        record = self._make_record()
        self.assertIn("keyword_count", record)
        self.assertIsInstance(record["keyword_count"], int)

    def test_record_has_blocks_analyzed(self):
        record = self._make_record()
        self.assertIn("blocks_analyzed", record)
        self.assertIsInstance(record["blocks_analyzed"], list)

    def test_record_has_total_lines_analyzed(self):
        record = self._make_record()
        self.assertIn("total_lines_analyzed", record)

    def test_record_has_total_proposed_drop_lines(self):
        record = self._make_record()
        self.assertIn("total_proposed_drop_lines", record)

    def test_record_has_total_estimated_tokens_saved(self):
        record = self._make_record()
        self.assertIn("total_estimated_tokens_saved", record)

    def test_record_has_prompt_total_chars(self):
        record = self._make_record()
        self.assertIn("prompt_total_chars", record)

    def test_record_has_prompt_estimated_tokens(self):
        record = self._make_record()
        self.assertIn("prompt_estimated_tokens", record)

    def test_block_type_enum_valid(self):
        record = self._make_record()
        for block_info in record["blocks_analyzed"]:
            self.assertIn(block_info["block_type"], self.VALID_BLOCK_TYPES,
                          f"Invalid block_type: {block_info['block_type']!r}")

    def test_estimated_tokens_saved_is_chars_div_4(self):
        from swe_pruner import build_record, segment_content_blocks, propose_drops, extract_goal_keywords
        # Create a block with known content for deterministic char count
        content = "irrelevant weather content today is sunny\n" * 5
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": f"## Scratchpad\n{content}",
            }
        }
        prompt = payload["tool_input"]["prompt"]
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication", "migration"])
        proposals = [(b, propose_drops(b, keywords)) for b in blocks]
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record = build_record(payload, proposals)
        # Verify formula: tokens = chars // 4
        for block_info in record["blocks_analyzed"]:
            dropped_chars = sum(
                len(blocks[0].lines[i])
                for start, end in block_info["proposed_drop_ranges"]
                for i in range(start, end)
                if i < len(blocks[0].lines)
            )
            expected_tokens = dropped_chars // 4
            self.assertEqual(block_info["estimated_tokens_saved"], expected_tokens)

    def test_build_record_never_raises_on_malformed_payload(self):
        from swe_pruner import build_record
        try:
            record = build_record({}, [])
            self.assertIsInstance(record, dict)
        except Exception as exc:
            self.fail(f"build_record raised on malformed payload: {exc}")

    def test_build_record_handles_none_payload(self):
        from swe_pruner import build_record
        try:
            record = build_record(None, [])  # type: ignore
            self.assertIsInstance(record, dict)
        except Exception as exc:
            self.fail(f"build_record raised on None payload: {exc}")


class TestJsonlFileMode(unittest.TestCase):
    """AC14: JSONL written with mode 0o600 (real invariant — 0o600 hardening)."""

    def test_jsonl_written_with_mode_0o600(self):
        from secure_jsonl import append_secure_jsonl
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics" / "session" / "swe-pruner.jsonl"
            record = {"timestamp": "2026-06-06T00:00:00Z", "agent_role": "test"}
            append_secure_jsonl(path, record)
            mode = stat.S_IMODE(os.stat(str(path)).st_mode)
            self.assertEqual(mode, 0o600,
                             f"File mode is {oct(mode)}, expected 0o600")

    def test_jsonl_content_is_valid_json(self):
        from secure_jsonl import append_secure_jsonl
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jsonl"
            record = {"key": "value", "number": 42}
            append_secure_jsonl(path, record)
            content = path.read_text()
            parsed = json.loads(content.strip())
            self.assertEqual(parsed["key"], "value")
            self.assertEqual(parsed["number"], 42)


class TestJsonlPathCascade(unittest.TestCase):
    """AC15: JSONL path uses three-tier cascade CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > HOME."""

    def test_jsonl_path_three_tier_cascade_plugin_data(self):
        """When CLAUDE_PLUGIN_DATA is set, JSONL goes there."""
        from swe_pruner import get_jsonl_path
        with tempfile.TemporaryDirectory() as plugin_data:
            with patch.dict(os.environ, {
                "CLAUDE_PLUGIN_DATA": plugin_data,
                "CLAUDE_SESSION_ID": "test-session",
            }, clear=False):
                path = get_jsonl_path()
            self.assertTrue(str(path).startswith(plugin_data),
                            f"Expected path under CLAUDE_PLUGIN_DATA={plugin_data}, got {path}")

    def test_jsonl_path_config_dir_fallback(self):
        """When CLAUDE_PLUGIN_DATA not set, CLAUDE_CONFIG_DIR is used."""
        from swe_pruner import get_jsonl_path
        with tempfile.TemporaryDirectory() as config_dir:
            env = {k: v for k, v in os.environ.items()
                   if k not in ("CLAUDE_PLUGIN_DATA",)}
            env["CLAUDE_CONFIG_DIR"] = config_dir
            env["CLAUDE_SESSION_ID"] = "test-session"
            with patch.dict(os.environ, env, clear=True):
                path = get_jsonl_path()
            self.assertTrue(str(path).startswith(config_dir),
                            f"Expected path under CLAUDE_CONFIG_DIR={config_dir}, got {path}")


class TestGoalHash(unittest.TestCase):
    """AC16: goal_hash is stable for identical keywords; is 16 hex chars."""

    def test_goal_hash_stable_for_identical_keywords(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild the authentication service\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record1 = build_record(payload, [])
            record2 = build_record(payload, [])
        self.assertEqual(record1["goal_hash"], record2["goal_hash"])

    def test_goal_hash_is_16_hex_chars(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild the authentication service\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record = build_record(payload, [])
        self.assertRegex(record["goal_hash"], r"^[0-9a-f]{16}$",
                         f"goal_hash is not 16 hex chars: {record['goal_hash']!r}")

    def test_goal_hash_different_for_different_keywords(self):
        from swe_pruner import build_record
        payload1 = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": "## Scratchpad\nbuild the authentication service\n",
            }
        }
        payload2 = {
            "tool_input": {
                "subagent_type": "database-engineer",
                "prompt": "## Scratchpad\nmigrate the database schema\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record1 = build_record(payload1, [])
            record2 = build_record(payload2, [])
        self.assertNotEqual(record1["goal_hash"], record2["goal_hash"])


class TestNoRawPromptContent(unittest.TestCase):
    """Security: build_record must NOT contain raw prompt content."""

    def test_build_record_excludes_raw_prompt_content(self):
        from swe_pruner import build_record
        secret = "SECRET_API_KEY=sk-123456abcdef"
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "prompt": f"## Scratchpad\n{secret}\nsome other content\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record = build_record(payload, [])
        self.assertNotIn(secret, json.dumps(record),
                         "Raw prompt content (including secrets) must not appear in build_record output")

    def test_build_record_excludes_task_id_from_prompt(self):
        from swe_pruner import build_record
        payload = {
            "tool_input": {
                "subagent_type": "software-engineer",
                "task_id": "task-abc-123",
                "prompt": "## Scratchpad\nbuild the service\n",
            }
        }
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}, clear=False):
            record = build_record(payload, [])
        self.assertIn("task_id", record,
                      "task_id should be present in record (from tool_input, not prompt)")
        self.assertEqual(record["task_id"], "task-abc-123")


if __name__ == "__main__":
    unittest.main()
