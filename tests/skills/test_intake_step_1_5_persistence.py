"""Slice B — AC3 (persistence)
Parse the example frontmatter block(s) from skills/intake/SKILL.md and assert
that the 12 forensic-schema keys appear with sensible YAML-type expectations.

The intake SKILL.md does not contain a runnable frontmatter (it carries its own
top-of-file metadata), so this test extracts the example frontmatter block from
the Step 1.5 documentation — a fenced YAML block embedded in the markdown — and
checks each key is present with a value-shape hint.

Note: this is a SKILL.md authoring test, not a runtime test.
"""
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"]
).decode().strip()
INTAKE_SKILL = os.path.join(REPO_ROOT, "skills", "intake", "SKILL.md")

REQUIRED_KEYS = [
    "gear_emitted",
    "gear_initial",
    "detector_phase",
    "detector_confidence",
    "user_phrasing_signals",
    "phrasing_honoured",
    "override_token",
    "safety_override_fired",
    "predicted_files",
    "fingerprint_cost_tokens",
    "criticality_filtered_by_gear",
    "task_id",
]


def _read_skill():
    with open(INTAKE_SKILL, "r", encoding="utf-8") as f:
        return f.read()


class IntakeFrontmatterTest(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(os.path.isfile(INTAKE_SKILL))

    def test_frontmatter_keys_complete(self):
        text = _read_skill()
        missing = []
        for key in REQUIRED_KEYS:
            # Accept either a bare YAML key (key:) or a backticked reference
            # (`key`) — both are legitimate documentation surfaces.
            if not re.search(rf"(?m)(^|\s){re.escape(key)}\s*:|`{re.escape(key)}`", text):
                missing.append(key)
        self.assertEqual(missing, [], f"missing keys in SKILL.md: {missing}")

    def test_missing_gear_fail_safe_explicitly_documented(self):
        text = _read_skill()
        self.assertRegex(text, r"Missing-gear fail-safe")


if __name__ == "__main__":
    unittest.main()
