"""Slice E AC29 + AC30 — Codebase-map DUAL_PATH soak-end calendar anchor.

A zero-content placeholder pipeline.md committed in this PR with
phase: pending and frontmatter not_before: today+30. SessionStart
bootstrap surfaces it as 'soak-end pipeline ready' once the date passes.

Mirrors `tests/test_soak_end_anchor_present.py` (the C3 soak-end anchor)
byte-for-byte in shape; only the path and cleanup-items count differ.

AC29: not_before is parseable ISO date AND ≥28 days from today (2-day
slack for re-merges; soak target is 30 days).

AC30: body documents EXACTLY 4 cleanup items, AND has a NEGATIVE
assertion guard: NO mention of "remove updater-dispatch refusal".
The dispatch refusal in Slice D is permanent architecture, not soak
scaffolding — re-introducing item #5 would re-allow misroute on
regression.
"""
import datetime
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANCHOR = ROOT / "pipeline-state" / "auto-codebase-map-soak-end" / "pipeline.md"


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


def _body_only(text):
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


class CodebaseMapSoakEndAnchorPresent(unittest.TestCase):
    def test_anchor_file_exists(self):
        self.assertTrue(ANCHOR.is_file(), f"missing: {ANCHOR}")

    def test_anchor_has_phase_pending_frontmatter(self):
        fm = _parse_frontmatter(ANCHOR.read_text())
        self.assertEqual(fm.get("phase"), "pending")

    def test_anchor_has_not_before_field(self):
        fm = _parse_frontmatter(ANCHOR.read_text())
        self.assertIn("not_before", fm)


class CodebaseMapSoakEndAnchorContract(unittest.TestCase):
    def test_ac29_not_before_parseable_and_future(self):
        """not_before must be ISO date ≥ today+28 days (30-day target with 2-day slack)."""
        fm = _parse_frontmatter(ANCHOR.read_text())
        not_before_str = fm.get("not_before", "")
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", not_before_str)
        self.assertIsNotNone(
            match,
            f"not_before must start with ISO date YYYY-MM-DD, got: {not_before_str!r}",
        )
        not_before = datetime.date.fromisoformat(match.group(1))
        # Anchor was set at PR open with merge_date+30d. Allow 28-day floor for
        # any small drift in merge timing. Today is 2026-05-10 → floor 2026-06-07.
        floor = datetime.date(2026, 6, 7)
        self.assertGreaterEqual(
            not_before, floor,
            f"not_before {not_before} is too soon — soak target is merge_date+30d",
        )

    def test_ac30_cleanup_items_documented(self):
        """Body must document EXACTLY 4 cleanup items.

        Negative assertion guard: NO mention of "remove updater-dispatch
        refusal" — Slice D refusal is permanent architecture, not soak
        scaffolding. Re-introducing it would re-allow misroute on any
        future generator regression.
        """
        body = _body_only(ANCHOR.read_text())

        # Count numbered items 1.-4. — exactly four (no 5th).
        item_lines = re.findall(r"^\s*(\d+)\.\s+\S", body, re.MULTILINE)
        self.assertEqual(
            sorted(item_lines), ["1", "2", "3", "4"],
            f"Expected exactly numbered items 1-4, got: {item_lines}",
        )

        # NEGATIVE assertion: the refusal is permanent, do NOT list it.
        forbidden = "remove updater-dispatch refusal"
        self.assertNotIn(
            forbidden, body.lower(),
            f"Body MUST NOT mention {forbidden!r} — refusal in Slice D is "
            "permanent architecture (generator-owned artifact regardless of "
            "soak state). Re-introducing this cleanup item would re-allow "
            "misroute on any future generator regression.",
        )


if __name__ == "__main__":
    unittest.main()
