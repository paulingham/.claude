"""Slice C AC-C0 — probe-result.md is persisted with claude version + verdict.

The pipeline either flips (GREEN) or holds (RED) on whether
`modified_tool_input` round-trips on the Agent matcher. Either way the
result MUST be persisted at the canonical path so future pipelines can
read the verdict without re-probing.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_RESULT = REPO_ROOT / "pipeline-state" \
    / "promote-advisory-hooks-enforcement" / "probe-result.md"


class ProbeResultMdPersisted(unittest.TestCase):
    def test_probe_result_md_persisted(self):
        self.assertTrue(PROBE_RESULT.exists(),
                        f"expected probe verdict file at {PROBE_RESULT}")
        body = PROBE_RESULT.read_text()
        self.assertIn("claude", body.lower(),
                      "probe-result.md must record claude version")
        self.assertTrue("GREEN" in body or "RED" in body,
                        "probe-result.md must declare GREEN or RED verdict")


if __name__ == "__main__":
    unittest.main()
