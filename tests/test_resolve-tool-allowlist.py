"""Smoke test the resolve-tool-allowlist.py stdin script.

Behavioural coverage of the resolver core lives in
test_tool_allowlist_resolver.py; this module pins the script's stdout
contract — three lines (decision, resolved, frontmatter) — that the
bash wrapper depends on for HIGH-2 frontmatter wiring.
"""
import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "hooks" / "_lib" / "resolve-tool-allowlist.py"


def _run(payload):
    return subprocess.run(
        ["python3", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=10)


class StdoutContractIsThreeLines(unittest.TestCase):
    """HIGH-2: third stdout line is the frontmatter-tools JSON list."""

    def test_known_role_emits_three_lines_with_frontmatter_list(self):
        result = _run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "allowed_tools": ["Read", "Write"]}})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), 3, f"expected 3 lines, got {lines!r}")
        decision, resolved_json, fm_json = lines
        self.assertIn(decision, {"SKIP", "LOG"})
        resolved = json.loads(resolved_json)
        self.assertIn("action", resolved)
        frontmatter = json.loads(fm_json)
        self.assertIsInstance(frontmatter, list)

    def test_unknown_role_emits_null_frontmatter_line(self):
        result = _run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "no-such-role-xyz"}})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), 3)
        # Loader returns None for unknown roles; that serialises to "null"
        self.assertEqual(lines[2], "null")


if __name__ == "__main__":
    unittest.main()
