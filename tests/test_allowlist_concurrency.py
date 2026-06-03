"""Concurrent JSONL append safety for the allowlist hook.

POSIX `O_APPEND` guarantees atomic appends below PIPE_BUF (~4KB on
Linux/macOS). Each emit line is well under that, so 8 simultaneous
hook fires must produce 8 standalone, valid JSON lines — no
interleaving, no truncation.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-allowlist.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _fire_hook(payload, env):
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True,
        text=True, timeout=10, env=env)


class ConcurrentLogAppendsAreLineSafe(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="conc-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def test_eight_concurrent_writers_produce_eight_valid_lines(self):
        session = f"test-conc-{uuid.uuid4()}"
        log_path = self.plugin_data / "metrics" / session / "tool-allowlist.jsonl"
        payload = json.dumps(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Read", "Write"]}})
        existing_pp = os.environ.get("PYTHONPATH", "")
        merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
        env = {**os.environ, "CLAUDE_SESSION_ID": session,
               "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
               "HOME": str(self.plugin_data),
               "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
               "PYTHONPATH": merged_pp}
        threads = [threading.Thread(target=_fire_hook, args=(payload, env))
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        lines = log_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 8)
        for line in lines:
            json.loads(line)  # MUST NOT raise


if __name__ == "__main__":
    unittest.main()
