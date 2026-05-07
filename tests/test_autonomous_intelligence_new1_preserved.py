"""AC4 + AC18 — NEW-1's domain-weighted floor formula preserved.

AC4 (fast-fail): the literal string 'min(0.85, floor + 0.05 * (N - 3))'
and its containing bullet are present in
rules/_detail/autonomous-intelligence.md after this PR's edits.

AC18 (comprehensive): the entire § Scratchpad → Instinct Promotion subsection
(from its '### Scratchpad → Instinct Promotion' header through the next
'###' or '##' boundary) byte-hashes to the value captured at PR-open time.
"""
import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "rules" / "_detail" / "autonomous-intelligence.md"

# Captured at PR-open time (verified from main branch HEAD before edits).
EXPECTED_SHA256 = "6f47cc8331abbca5867e2b38f1731cf57d0c0edd99251f263ed7c3e6bb5c7170"


def _section_text():
    text = TARGET.read_text()
    match = re.search(
        r"(### Scratchpad → Instinct Promotion\n.*?)(?=\n###|\n##\s|\Z)",
        text,
        re.DOTALL,
    )
    return match.group(1) if match else None


class DomainWeightedFloorFormulaPreserved(unittest.TestCase):
    def test_domain_weighted_floor_formula_preserved(self):
        section = _section_text()
        self.assertIsNotNone(section, "§ Scratchpad → Instinct Promotion not found")
        self.assertIn("min(0.85, floor + 0.05 * (N - 3))", section)
        self.assertIn("workflow: 0.5", section)
        self.assertIn("testing: 0.6", section)
        self.assertIn("code-style: 0.6", section)
        self.assertIn("architecture: 0.7", section)
        self.assertIn("security: 0.7", section)


class ScratchpadToInstinctPromotionSectionHashUnchanged(unittest.TestCase):
    def test_scratchpad_to_instinct_promotion_section_sha256_unchanged(self):
        section = _section_text()
        self.assertIsNotNone(section)
        actual = hashlib.sha256(section.encode("utf-8")).hexdigest()
        self.assertEqual(
            actual, EXPECTED_SHA256,
            "§ Scratchpad → Instinct Promotion bytes have changed. "
            "If this edit is intentional, recompute the expected SHA-256.",
        )


if __name__ == "__main__":
    unittest.main()
