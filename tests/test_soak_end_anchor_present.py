"""AC17 — Soak-end calendar anchor.

A zero-content placeholder pipeline.md is committed in this PR with
phase: pending and frontmatter not_before: {merge_date+30d}. SessionStart
bootstrap surfaces it as 'soak-end pipeline ready' once the date passes.

This test asserts the file exists, has frontmatter with phase==pending and
a parseable not_before in ISO 8601 (>= today + 28d as a sanity floor —
30d is the target but allow 2 days of slack for migration timing).
"""
import datetime
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANCHOR = ROOT / "pipeline-state" / "wave2a-c3-soak-end" / "pipeline.md"


def _parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


class SoakEndStateFileExistsWithNotBeforeField(unittest.TestCase):
    def test_anchor_file_exists(self):
        self.assertTrue(ANCHOR.is_file(), f"missing: {ANCHOR}")

    def test_anchor_has_phase_pending_frontmatter(self):
        fm = _parse_frontmatter(ANCHOR.read_text())
        self.assertEqual(fm.get("phase"), "pending")

    def test_anchor_has_not_before_field(self):
        fm = _parse_frontmatter(ANCHOR.read_text())
        self.assertIn("not_before", fm)

    def test_not_before_is_iso8601_at_least_28_days_out(self):
        fm = _parse_frontmatter(ANCHOR.read_text())
        not_before_str = fm.get("not_before", "")
        # Accept YYYY-MM-DD or full ISO 8601.
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", not_before_str)
        self.assertIsNotNone(
            match,
            f"not_before must start with ISO date YYYY-MM-DD, got: {not_before_str!r}",
        )
        not_before = datetime.date.fromisoformat(match.group(1))
        # Anchor was set at PR open with merge_date+30d. Allow 28 day floor for
        # any small drift in merge timing.
        floor = datetime.date(2026, 6, 4)
        self.assertGreaterEqual(
            not_before, floor,
            f"not_before {not_before} is too soon — soak target is merge_date+30d",
        )


if __name__ == "__main__":
    unittest.main()
