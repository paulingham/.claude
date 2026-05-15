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
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EMITTER = REPO_ROOT / "hooks" / "reflect-token-emit.sh"


class ReflectTokenEmittedForHighFloorDeviation(unittest.TestCase):
    """The emitter writes a JSON file with the deviation id, initial
    `acknowledged: false`, the verification path, and a timestamp.
    """

    def _run(self, deviation_id, session, env_extra=None):
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["bash", str(EMITTER), deviation_id],
            capture_output=True, text=True, timeout=10, env=env)

    def test_emits_token_with_acknowledged_false(self):
        session = f"test-{uuid.uuid4()}"
        deviation_id = "slice-b-high-floor-named-deviation"
        token_path = (Path.home() / ".claude" / "metrics" / session
                      / "reflect-tokens" / f"{deviation_id}.json")
        try:
            result = self._run(deviation_id, session)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(token_path.exists(),
                            f"expected token at {token_path}")
            payload = json.loads(token_path.read_text())
            self.assertEqual(payload["deviation_id"], deviation_id)
            self.assertFalse(payload["acknowledged"])
            self.assertIn("timestamp", payload)
        finally:
            if token_path.exists():
                token_path.unlink()
            parent = token_path.parent
            if parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    pass

    def test_idempotent_does_not_clobber_acknowledged_true(self):
        # If the operator has already flipped acknowledged=true, re-emitting
        # the token MUST NOT reset it to false.
        session = f"test-{uuid.uuid4()}"
        deviation_id = "slice-b-high-floor-named-deviation"
        token_path = (Path.home() / ".claude" / "metrics" / session
                      / "reflect-tokens" / f"{deviation_id}.json")
        try:
            # First write — initial false.
            self._run(deviation_id, session)
            # Operator flips it.
            payload = json.loads(token_path.read_text())
            payload["acknowledged"] = True
            token_path.write_text(json.dumps(payload))
            # Re-emit — must not overwrite acknowledgment.
            self._run(deviation_id, session)
            payload = json.loads(token_path.read_text())
            self.assertTrue(payload["acknowledged"],
                            "re-emit must not clobber acknowledged=true")
        finally:
            if token_path.exists():
                token_path.unlink()
            parent = token_path.parent
            if parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    pass

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
