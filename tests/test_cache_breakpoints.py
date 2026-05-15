"""Slice C AC-C1 — persona-tail anchor promoted from `deferred` to active status.

`hooks/_lib/resolve-cache-breakpoints.py` resolves the cache anchor payload.
Slice C promotes `persona-tail` so the resolved payload includes ≥1 anchor
with `name == "persona-tail"` and status != "deferred".
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER = REPO_ROOT / "hooks" / "_lib" / "resolve-cache-breakpoints.py"


def _run_resolver() -> dict:
    """Pipe an Agent-tool envelope into the resolver and parse line 2."""
    envelope = json.dumps({"tool_name": "Agent",
                           "tool_input": {"subagent_type": "software-engineer"}})
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
    result = subprocess.run(
        ["python3", str(RESOLVER)],
        input=envelope, capture_output=True, text=True, env=env, timeout=10)
    lines = result.stdout.strip().split("\n")
    return json.loads(lines[1])


class PersonaTailAnchorIsActive(unittest.TestCase):
    def test_persona_tail_anchor_active(self):
        resolved = _run_resolver()
        anchors = resolved.get("anchors", [])
        persona = [a for a in anchors if a.get("name") == "persona-tail"]
        self.assertEqual(
            len(persona), 1,
            f"resolver must emit exactly one persona-tail anchor; got {len(persona)}")
        self.assertNotEqual(
            persona[0].get("status"), "deferred",
            "persona-tail anchor must be promoted from `deferred` (Slice C C.1)")


if __name__ == "__main__":
    unittest.main()
