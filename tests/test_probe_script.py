"""Slice C AC-C-AUTHOR — hooks/probe-modified-tool-input.sh exists,
is executable, and emits the expected modified_tool_input envelope on
stdout.

This is the prerequisite probe script for any future Slice C-GREEN
flip. The script itself is run only by operators (registered temporarily
in settings.json); CI smoke-tests the shape so prose drift doesn't
silently break the future re-probe path.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE = REPO_ROOT / "hooks" / "probe-modified-tool-input.sh"


class ProbeScriptExistsExecutableAndOutputsExpectedShape(unittest.TestCase):
    def test_probe_script_exists_executable_and_outputs_expected_shape(self):
        self.assertTrue(PROBE.exists(), f"probe missing at {PROBE}")
        self.assertTrue(os.access(PROBE, os.X_OK), "probe is not executable")
        # Drive stdin with a minimal Agent payload and check stdout shape
        proc = subprocess.run(
            ["bash", str(PROBE)],
            input='{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}',
            capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 0)
        # stdout MUST be a JSON envelope with decision and modified_tool_input
        parsed = json.loads(proc.stdout.strip())
        self.assertEqual(parsed["decision"], "approve")
        self.assertIn("modified_tool_input", parsed)
        self.assertIn("thinking", parsed["modified_tool_input"])
        self.assertIn("effort", parsed["modified_tool_input"]["thinking"])


if __name__ == "__main__":
    unittest.main()
