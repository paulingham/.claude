"""Slice F AC31 — Rules-doc edit grep contract.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice F (AC31).

The rules document `rules/_detail/autonomous-intelligence.md` MUST call
out `codebase-map.md` as a generated artifact in two places:

1. The role × sub-file injection table (lines 127-140 region) gets a
   footnote against the `codebase-map.md` row pointing at the new
   sub-section.
2. The `## Sub-file Layout & Soak` region (lines 148-165 region) gets a
   new sub-section documenting the codebase-map-specific 30-day window,
   the 4-item cleanup list, and the writer-MUST-NOT injunction.

This file's tests are deliberately structural (grep) — content changes
flow through the existing soak-end-anchor test (AC30) and integration
tests (AC32-AC34). The point of AC31 is to assert the rules document
agrees with the soak-end placeholder pipeline on the four cleanup items
and the 30-day window.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DOC = ROOT / "rules" / "_detail" / "autonomous-intelligence.md"


class RulesDocCodebaseMapEdits(unittest.TestCase):
    """AC31 — codebase-map.md is named as a generated artifact + soak prose."""

    def setUp(self):
        self.assertTrue(RULES_DOC.is_file(), f"missing: {RULES_DOC}")
        self.text = RULES_DOC.read_text()

    def test_ac31_codebase_map_row_has_generated_artifact_footnote(self):
        """The architect-row table cell mentions 'generated artifact'."""
        # The row format from line 129:
        # | `architect` | `codebase-map.md`, `patterns.md`, `fragility.md` |
        # The footnote MUST live in the SAME row (e.g., a `*generated artifact*`
        # marker after `codebase-map.md`) — not in a sibling table or comment.
        rows = [
            ln for ln in self.text.splitlines()
            if "architect" in ln and "codebase-map.md" in ln
        ]
        self.assertTrue(rows, "architect row not found")
        joined = " ".join(rows).lower()
        self.assertIn(
            "generated artifact", joined,
            "architect row MUST flag codebase-map.md as a generated artifact",
        )

    def test_ac31_soak_section_documents_30_day_window(self):
        """The codebase-map sub-section names the 30-day window."""
        # We look for the literal phrase "30-day" (with hyphen — matches the
        # C3 soak prose precedent at line 163) inside a region that ALSO
        # mentions codebase-map. This is a content-coherence check, not a
        # stand-alone occurrence check (the file already says "30-day" once
        # for the C3 soak — we want a SECOND mention paired with codebase-map).
        codebase_map_sections = self._codebase_map_paragraphs()
        self.assertTrue(
            codebase_map_sections,
            "no paragraph mentions codebase-map outside the table row",
        )
        joined = "\n".join(codebase_map_sections).lower()
        self.assertIn(
            "30-day", joined,
            "codebase-map soak section MUST name the 30-day window "
            "(matches the C3 precedent at line 163 + the soak-end anchor "
            "AC29 floor of merge_date+30d)",
        )

    def test_ac31_soak_section_documents_four_cleanup_items(self):
        """The codebase-map sub-section names the 4-item cleanup list."""
        sections = self._codebase_map_paragraphs()
        joined = "\n".join(sections).lower()
        self.assertIn(
            "4", joined,
            "codebase-map soak section MUST mention the 4-item cleanup list "
            "(soak-end anchor AC30 locks the count at exactly 4)",
        )
        # The sub-section must point readers at the soak-end pipeline file
        # so the cleanup-item count is discoverable from the rules doc.
        self.assertIn(
            "auto-codebase-map-soak-end",
            joined,
            "codebase-map soak section MUST reference the soak-end pipeline "
            "anchor file path so the cleanup-items list is discoverable",
        )

    def test_ac31_writers_must_not_dispatch_updater(self):
        """The sub-section names the updater-dispatch refusal."""
        sections = self._codebase_map_paragraphs()
        joined = "\n".join(sections).lower()
        # AC31 explicitly requires the prose: "writers MUST NOT include
        # codebase-map.md in updater dispatch" (or equivalent — we accept
        # any wording that pairs 'updater' with a refusal verb).
        self.assertRegex(
            joined,
            r"updater[\s\S]{0,200}(refus|must not|never|excluded|do not)",
            "codebase-map soak section MUST name the permanent updater-"
            "dispatch refusal (Slice D architecture).",
        )

    # --- helpers ---

    def _codebase_map_paragraphs(self) -> list[str]:
        """Return paragraphs that mention codebase-map (excluding table row)."""
        out: list[str] = []
        # Split on blank lines; keep paragraphs that mention codebase-map
        # but skip the table row (single-line, has '|' delimiters).
        for block in re.split(r"\n\n+", self.text):
            if "codebase-map" not in block:
                continue
            stripped = block.strip()
            # Skip a pure table-row block.
            if stripped.startswith("|") and stripped.endswith("|"):
                continue
            out.append(block)
        return out


if __name__ == "__main__":
    unittest.main()
