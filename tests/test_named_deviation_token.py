"""Reflect-token writer test — slice-b-high-floor-named-deviation.

`hooks/reflect-token-emit.sh` writes a JSON token under
`metrics/{session}/reflect-tokens/{deviation_id}.json` with initial
`acknowledged: false`. The Reflect step (or operator) flips this to `true`
to acknowledge the named deviation; the orchestrator's reflect gate halts
when an unacknowledged token is present.

The TOKEN WRITER is what this slice ships; the gate enforcement is
orchestrator work outside Slice B's scope.
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
EMITTER = REPO_ROOT / "hooks" / "reflect-token-emit.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


class ReflectTokenEmittedForHighFloorDeviation(unittest.TestCase):
    """The emitter writes a JSON file with the deviation id, initial
    `acknowledged: false`, the verification path, and a timestamp.
    """

    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="devtoken-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _token_path(self, session, deviation_id):
        return (self.plugin_data / "metrics" / session
                / "reflect-tokens" / f"{deviation_id}.json")

    def _run(self, deviation_id, session, env_extra=None):
        existing_pp = os.environ.get("PYTHONPATH", "")
        merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
        env = {**os.environ, "PYTHONPATH": merged_pp,
               "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
               "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
               "HOME": str(self.plugin_data),
               "CLAUDE_SESSION_ID": session}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["bash", str(EMITTER), deviation_id],
            capture_output=True, text=True, timeout=10, env=env)

    def test_emits_token_with_acknowledged_false(self):
        session = f"test-{uuid.uuid4()}"
        deviation_id = "slice-b-high-floor-named-deviation"
        token_path = self._token_path(session, deviation_id)
        result = self._run(deviation_id, session)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(token_path.exists(), f"expected token at {token_path}")
        payload = json.loads(token_path.read_text())
        self.assertEqual(payload["deviation_id"], deviation_id)
        self.assertFalse(payload["acknowledged"])
        self.assertIn("timestamp", payload)

    def test_idempotent_does_not_clobber_acknowledged_true(self):
        session = f"test-{uuid.uuid4()}"
        deviation_id = "slice-b-high-floor-named-deviation"
        token_path = self._token_path(session, deviation_id)
        self._run(deviation_id, session)
        payload = json.loads(token_path.read_text())
        payload["acknowledged"] = True
        token_path.write_text(json.dumps(payload))
        self._run(deviation_id, session)
        payload = json.loads(token_path.read_text())
        self.assertTrue(payload["acknowledged"],
                        "re-emit must not clobber acknowledged=true")

    def test_rejects_empty_deviation_id(self):
        session = f"test-{uuid.uuid4()}"
        result = self._run("", session)
        # Exit 2 distinguishes usage error from missing-file 127 and mkdir
        # exit 1; locks the contract that the emitter actively rejects.
        self.assertEqual(result.returncode, 2,
                         "empty deviation_id must exit 2 (usage error)")
        self.assertIn("deviation_id required", result.stderr)


if __name__ == "__main__":
    unittest.main()
