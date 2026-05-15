"""Slice C AC-C4 — READ_RATIO_TARGET raised from 0.60 to 0.65.

Three assertions (Slice C extends Slice A's lockstep test):
  (a) `READ_RATIO_TARGET = 0.65` appears verbatim once in skills/cache-audit/SKILL.md
  (b) The rendered threshold sentence in `## Below-Target Sessions` contains the
      literal `"0.65"` value (single source of truth — no copy-paste drift).
  (c) No rival numeric thresholds (0.50, 0.60, 0.70) appear in SKILL.md body.

The flip to 0.70 is gated by the new `cache-flip-gate` skill (Slice C C.4 path c).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"


class ReadRatioTargetRaisedTo065(unittest.TestCase):
    def test_target_raised_to_0_65(self):
        text = SKILL.read_text()
        # (a) verbatim once.
        matches = re.findall(r"READ_RATIO_TARGET\s*=\s*0\.65", text)
        self.assertEqual(
            len(matches), 1,
            "`READ_RATIO_TARGET = 0.65` must appear exactly once (single SSOT). "
            f"Found {len(matches)} occurrences.")
        # (b) rendered in `## Below-Target Sessions` section.
        section_match = re.search(
            r"##\s*Below-Target Sessions\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(
            section_match,
            "SKILL.md must have a `## Below-Target Sessions` section")
        section_body = section_match.group(1)
        self.assertIn(
            "0.65", section_body,
            "`## Below-Target Sessions` threshold sentence must render "
            "the literal `0.65` value")
        # (c) No rival numeric thresholds appear (scan body excluding frontmatter).
        body_after_fm = re.sub(r"^---\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
        for rival in ("0.50", "0.60", "0.70"):
            self.assertNotIn(
                rival, body_after_fm,
                f"Rival numeric threshold `{rival}` must not appear in "
                f"SKILL.md body — only `0.65` is the configured target.")


if __name__ == "__main__":
    unittest.main()
