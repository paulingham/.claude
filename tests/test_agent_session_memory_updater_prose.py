"""AC25 (Slice D) — `agents/session-memory-updater.md` marks codebase-map
as a generator-owned artifact at all three required surfaces.

Per plan §3 Slice D (D4):
- Description (line 3) no longer lists `codebase-map` among writable sub-files.
- Inputs/targetSection enum (line 37) no longer includes `codebase-map`.
- Capture-rules (line 60) explicitly says codebase-map.md is generator-owned
  AND that the refusal is **permanent** (NOT soak scaffolding).

The "permanent" wording guards against future re-introduction during the
30-day soak window — generated artifacts are generator-owned regardless of
soak state.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DOC = ROOT / "agents" / "session-memory-updater.md"


class CodebaseMapMarkedGenerated(unittest.TestCase):
    def setUp(self):
        self.body = AGENT_DOC.read_text()

    def test_description_no_longer_lists_codebase_map_as_writable(self):
        # Line 3 description: was "codebase-map / build-test / patterns / fragility";
        # codebase-map should be removed (or framed as generator-owned).
        first_block = self.body.split("---", 2)[1]  # frontmatter
        # The frontmatter description must not list codebase-map alongside the
        # other writable sub-files.
        self.assertNotRegex(
            first_block,
            r"codebase-map\s*/\s*build-test",
            "description must not list codebase-map as a writable sub-file",
        )

    def test_target_section_enum_excludes_codebase_map(self):
        # The `targetSection` input line previously listed accepted enum
        # values inside `(... )`. After the edit, codebase-map is NOT in
        # that parenthesised enum.
        #
        # We allow explanatory prose AFTER the parenthesised enum to mention
        # codebase-map (defence-in-depth note that the section is rejected),
        # but the enum tuple itself must list ONLY `build-test`, `patterns`,
        # `fragility` — the three writable sections.
        target_section_lines = [
            ln for ln in self.body.splitlines() if "targetSection`" in ln
        ]
        self.assertTrue(target_section_lines, "no `targetSection` line found")
        for line in target_section_lines:
            # Extract the FIRST `(...)` group on the line — that's the
            # accepted-enum list.
            match = re.search(r"\(([^)]*)\)", line)
            self.assertIsNotNone(
                match,
                f"targetSection line missing parenthesised enum: {line!r}",
            )
            enum_body = match.group(1)
            self.assertNotIn(
                "codebase-map", enum_body,
                f"codebase-map still in accepted-enum tuple: {enum_body!r}",
            )

    def test_capture_rules_call_out_codebase_map_as_generator_owned(self):
        # Capture-rules block must explicitly name codebase-map as
        # generator-owned + tell the agent not to edit it.
        self.assertIn("codebase-map", self.body)
        # Must say generator-owned (or equivalent phrasing).
        self.assertRegex(
            self.body,
            r"codebase-map[^\n]*generator-owned",
            "capture-rules must call codebase-map generator-owned",
        )

    def test_refusal_marked_permanent(self):
        # AC25 H3 wording: "permanent — generated artifacts are
        # generator-owned regardless of soak state."
        # We check for the load-bearing phrase, allowing minor wording variants.
        self.assertRegex(
            self.body,
            r"permanent.*generator-owned.*regardless of soak state",
            "capture-rules must explicitly mark refusal as permanent",
        )


if __name__ == "__main__":
    unittest.main()
