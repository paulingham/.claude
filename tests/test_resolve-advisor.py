"""Path-validation regression tests for hooks/_lib/resolve-advisor.py.

The bulk of the resolver suite lives in `test_advisor_resolver.py` (matches the
module being tested). This file exists to satisfy the tdd-guard naming
convention for the stdin entry script and to keep the path-traversal HIGH
regression tied 1:1 to the file under test.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

RESOLVER_SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "_lib" / "resolve-advisor.py"


def _run(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["python3", str(RESOLVER_SCRIPT)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


class TraversalSubagentTypeRejected(unittest.TestCase):
    """HIGH regression — security-engineer review round 1.
    Mirrors test_advisor_resolver.ResolverRejectsTraversalSubagentType so the
    behaviour is also asserted against the file under test by name."""

    def test_traversal_subagent_type_does_not_load_attacker_frontmatter(self):
        evil_dir = Path("/tmp/sec-poc-test-resolve-advisor")
        evil_file = evil_dir / "evil.md"
        evil_dir.mkdir(parents=True, exist_ok=True)
        evil_file.write_text(
            "---\nexecutor: ATTACKER-CONTROLLED-EXECUTOR\n"
            "advisor: ATTACKER-CONTROLLED-ADVISOR\n---\n")
        try:
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type":
                                      "../../../../tmp/sec-poc-test-resolve-advisor/evil"}}
            result = _run(payload, env={"ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            _decision, resolved_json = result.stdout.strip().splitlines()
            resolved = json.loads(resolved_json)
            self.assertNotEqual(resolved.get("executor"), "ATTACKER-CONTROLLED-EXECUTOR")
            self.assertEqual(resolved.get("source"), "no-pairing-frontmatter")
        finally:
            if evil_file.exists():
                evil_file.unlink()
            if evil_dir.exists():
                evil_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
