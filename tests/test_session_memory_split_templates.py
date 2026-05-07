"""AC1 — Sub-file templates exist with correct shape.

All 5 sub-file templates exist under session-memory/config/templates/, each
with exactly one '# {Title}' header line and one '_{italic description}_'
line, and config/template.md (the index) references all 5.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "session-memory" / "config" / "templates"
INDEX = ROOT / "session-memory" / "config" / "template.md"
SUBFILES = ("codebase-map", "build-test", "patterns", "fragility", "active-work")


class AllFiveTemplatesExistWithHeaderAndDescription(unittest.TestCase):
    def test_all_five_template_files_exist(self):
        for sub in SUBFILES:
            path = TEMPLATES_DIR / f"{sub}.md"
            self.assertTrue(path.is_file(), f"missing: {path}")

    def test_each_template_has_exactly_one_h1_header(self):
        for sub in SUBFILES:
            text = (TEMPLATES_DIR / f"{sub}.md").read_text()
            headers = [l for l in text.splitlines() if re.match(r"^# [^#]", l)]
            self.assertEqual(
                len(headers), 1,
                f"{sub}.md must have exactly one '# Title' line, found {len(headers)}",
            )

    def test_each_template_has_exactly_one_italic_description(self):
        for sub in SUBFILES:
            text = (TEMPLATES_DIR / f"{sub}.md").read_text()
            italics = [l for l in text.splitlines() if re.match(r"^_.+_\s*$", l)]
            self.assertEqual(
                len(italics), 1,
                f"{sub}.md must have exactly one '_…_' line, found {len(italics)}",
            )

    def test_index_template_references_all_five_subfiles(self):
        body = INDEX.read_text()
        for sub in SUBFILES:
            self.assertIn(
                f"{sub}.md", body,
                f"config/template.md must reference {sub}.md",
            )


if __name__ == "__main__":
    unittest.main()
