"""AC5 — `phases.pdr_rtv.fallback_reason` enum extended from 3 to 4
values to include `missing-meta`.

The enum is the single source of truth in `protocols/autonomous-intelligence.md`
and is mirrored in `orchestrator/parallel-dispatch-details.md § PDR-RTV step 6`.
Both surfaces must list the four values:
  - `worktree-cap-exceeded`
  - `insufficient-green-builds`
  - `all-finalists-rejected`
  - `missing-meta` (NEW)

Mirror is enforced by the test below — both files must declare all four
values inside their respective sections (autonomous-intelligence's
`phases.pdr_rtv` field reference, parallel-dispatch's PDR-RTV step 6).
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_PATH = REPO_ROOT / "protocols" / "autonomous-intelligence.md"
DISPATCH_PATH = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"

EXPECTED_VALUES = {
    "worktree-cap-exceeded",
    "insufficient-green-builds",
    "all-finalists-rejected",
    "missing-meta",
}


def _phases_pdr_rtv_row(text: str) -> str:
    # The autonomous-intelligence row matching `phases.pdr_rtv` is one
    # very long markdown table line. Locate by anchor and return the line.
    for line in text.splitlines():
        if "phases.pdr_rtv" in line and "fallback_reason" in line:
            return line
    return ""


def _pdr_rtv_step_6_section(text: str) -> str:
    # Slice from PDR-RTV section header up to the next `### ` heading.
    match = re.search(
        r"### PDR-RTV Build Team Dispatch.*?(?=^### )",
        text,
        flags=re.S | re.M,
    )
    return match.group(0) if match else ""


class PhasesPdrRtvFallbackReasonEnumIncludesMissingMeta(unittest.TestCase):
    def test_autonomous_intelligence_lists_all_four_values(self) -> None:
        text = AI_PATH.read_text(encoding="utf-8")
        row = _phases_pdr_rtv_row(text)
        self.assertTrue(row, "phases.pdr_rtv row not found in autonomous-intelligence.md")
        for value in EXPECTED_VALUES:
            self.assertIn(
                f'"{value}"',
                row,
                f"autonomous-intelligence.md phases.pdr_rtv enum missing {value!r}",
            )

    def test_parallel_dispatch_step_6_lists_all_four_values(self) -> None:
        text = DISPATCH_PATH.read_text(encoding="utf-8")
        section = _pdr_rtv_step_6_section(text)
        self.assertTrue(section, "PDR-RTV section not found in parallel-dispatch-details.md")
        # Step 6 is the verdict-and-merge step; the enum is documented in
        # the bullet list AND in the pipeline-state YAML block below it.
        for value in EXPECTED_VALUES:
            self.assertIn(
                value,
                section,
                f"parallel-dispatch-details.md PDR-RTV section missing {value!r}",
            )


if __name__ == "__main__":
    unittest.main()
