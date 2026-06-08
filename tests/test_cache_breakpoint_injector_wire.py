"""Slice C AC-C5 — cache-breakpoint-injector.sh emits `cache_flag: true` token.

The PreToolUse:Agent hook emits one JSONL record per spawn to
`metrics/{session}/cache-injections.jsonl`. Slice C requires the resolved
payload contains the literal token `cache_flag: true` (with `enable_prompt_caching`
intent — the SDK consumer is out-of-tree per C.3 escalation, but the in-tree
wire emission is testable here).

NOTE: This file exists ONLY in Slice C (Slice B uses a different filename
`test_hook_injection_schema.py`). No merge conflict.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "cache-breakpoint-injector.sh"


class CacheFlagTokenEmitted(unittest.TestCase):
    def test_jsonl_emits_cache_flag_token(self):
        envelope = json.dumps({
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "software-engineer"},
        })
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["HOME"] = td
            env["CLAUDE_SESSION_ID"] = "slice-c-test"
            env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
            # Runtime state (metrics) was relocated to HARNESS_DATA
            # (CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > $HOME/.claude). Point it
            # at the hermetic home so the write lands where the assertion reads.
            env["CLAUDE_PLUGIN_DATA"] = str(Path(td) / ".claude")
            # Run hook
            subprocess.run(
                ["bash", str(HOOK)], input=envelope,
                capture_output=True, text=True, env=env, timeout=30)
            jsonl = Path(td) / ".claude" / "metrics" / "slice-c-test" / "cache-injections.jsonl"
            self.assertTrue(
                jsonl.exists(),
                f"hook must write {jsonl} on Agent spawn; got tree: "
                f"{[p for p in Path(td).rglob('*.jsonl')]}")
            line = jsonl.read_text().strip().splitlines()[-1]
            record = json.loads(line)
            resolved = record.get("resolved", {})
            self.assertTrue(
                resolved.get("cache_flag") is True,
                f"resolved.cache_flag must be literal `true`; got {resolved}")


if __name__ == "__main__":
    unittest.main()
