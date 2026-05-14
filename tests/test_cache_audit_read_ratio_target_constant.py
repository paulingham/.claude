"""Slice A AC-A8 — READ_RATIO_TARGET is a single named constant of 0.60.

Three assertions:
  (a) `READ_RATIO_TARGET = 0.60` appears verbatim once in skills/cache-audit/SKILL.md
  (b) The rendered threshold sentence in `## Below-Target Sessions` contains the
      literal `"0.60"` value (single source of truth — no copy-paste drift).
  (c) No rival numeric thresholds (0.50, 0.70, 0.65) appear in SKILL.md.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"


class ReadRatioTargetIsSingleNamedConstant(unittest.TestCase):
    def test_read_ratio_target_is_single_constant_at_0_60_and_renders_in_report(self):
        text = SKILL.read_text()
        # (a) verbatim once.
        matches = re.findall(r"READ_RATIO_TARGET\s*=\s*0\.60", text)
        self.assertEqual(
            len(matches), 1,
            "`READ_RATIO_TARGET = 0.60` must appear exactly once (single SSOT). "
            f"Found {len(matches)} occurrences.")
        # (b) rendered in `## Below-Target Sessions` section.
        # Pull just the Below-Target Sessions section body.
        section_match = re.search(
            r"##\s*Below-Target Sessions\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(
            section_match,
            "SKILL.md must have a `## Below-Target Sessions` section")
        section_body = section_match.group(1)
        self.assertIn(
            "0.60", section_body,
            "`## Below-Target Sessions` threshold sentence must render "
            "the literal `0.60` value")
        # (c) No rival numeric thresholds appear (substring match on body
        # excluding the version string and YAML frontmatter to avoid noise).
        # We scan only the body section bodies.
        body_after_fm = re.sub(r"^---\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
        for rival in ("0.50", "0.70", "0.65"):
            self.assertNotIn(
                rival, body_after_fm,
                f"Rival numeric threshold `{rival}` must not appear in "
                f"SKILL.md body — only `0.60` is the configured target.")


if __name__ == "__main__":
    unittest.main()
