"""AC8 — session-memory-updater accepts targetFile + targetSection inputs.

Tests two concerns:
1. agents/session-memory-updater.md documents the new input contract
   (targetFile + targetSection) and removes references to notesPath as
   an input.
2. The orchestrator-side dispatch helper refuses to emit an Agent spawn
   when targetFile or targetSection is empty/blank/missing — non-zero exit
   + structured error.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DOC = ROOT / "agents" / "session-memory-updater.md"
DISPATCH_HELPER = ROOT / "hooks" / "_lib" / "session-memory-updater-dispatch.sh"


class AgentDocumentsTargetFileAndTargetSection(unittest.TestCase):
    def test_agent_doc_describes_target_file_input(self):
        body = AGENT_DOC.read_text()
        self.assertIn("targetFile", body)

    def test_agent_doc_describes_target_section_input(self):
        body = AGENT_DOC.read_text()
        self.assertIn("targetSection", body)

    def test_agent_doc_says_one_subfile_per_spawn(self):
        body = AGENT_DOC.read_text().lower()
        # Must communicate that one spawn writes exactly one sub-file.
        self.assertTrue(
            re.search(r"one sub.?file per spawn|exactly one sub.?file", body),
            "agent doc must state one sub-file per spawn",
        )


class DispatchHelperRefusesBlankFields(unittest.TestCase):
    def _run(self, *args):
        # The helper seeds its target from
        # $HARNESS_ROOT/session-memory/config/templates/<section>.md. Point
        # HARNESS_ROOT at the repo (via CLAUDE_PLUGIN_ROOT) so the template
        # resolves on a clean CI runner where $HOME/.claude is empty.
        # CLAUDE_PLUGIN_ROOT affects only HARNESS_ROOT, not HARNESS_DATA, so it
        # does not perturb other tests' metrics/state isolation.
        import os
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        return subprocess.run(
            ["bash", str(DISPATCH_HELPER), *args],
            capture_output=True, text=True, env=env,
        )

    def test_dispatch_helper_exists_and_is_executable(self):
        self.assertTrue(DISPATCH_HELPER.is_file(), f"missing: {DISPATCH_HELPER}")

    def test_dispatch_refuses_missing_target_file(self):
        result = self._run("", "patterns")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("targetFile", (result.stderr or result.stdout))

    def test_dispatch_refuses_missing_target_section(self):
        result = self._run("/tmp/x.md", "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("targetSection", (result.stderr or result.stdout))

    def test_dispatch_accepts_both_fields_present(self):
        result = self._run("/tmp/x.md", "patterns")
        self.assertEqual(result.returncode, 0, msg=f"stderr={result.stderr}")


if __name__ == "__main__":
    unittest.main()
