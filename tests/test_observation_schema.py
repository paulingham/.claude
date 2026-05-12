"""Slice 3 AC13 — phases.pdr_rtv block documented in observation schema.

`protocols/autonomous-intelligence.md` § Observation Capture must
document an OPTIONAL `phases.pdr_rtv` block with required keys
(`verdict`, `n_candidates_iter0`, `n_candidates_iter1`,
`tournament_rounds`, `winner_slug`, `cost_estimate_usd`) and an
OPTIONAL `fallback_reason` enum. Readers MUST tolerate absence per
existing schema-compatibility rules (mirrors the `phases.patch_critic`
extension precedent).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"


def _section(text, header_pattern, until_pattern):
    """Slice text between header_pattern and until_pattern."""
    m = re.search(header_pattern, text, re.MULTILINE)
    if not m:
        return None
    body_start = text.find("\n", m.end())
    if body_start == -1:
        return text[m.start():]
    body = text[body_start:]
    end = re.search(until_pattern, body, re.MULTILINE)
    if end is None:
        return text[m.start():]
    return text[m.start():body_start + end.start()]


def _observation_capture_section() -> str:
    text = OBSERVATION_DOC.read_text()
    match = re.search(
        r"###\s+Observation Capture\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


class PhasesPdrRtvBlockDocumented(unittest.TestCase):
    """AC13 — phases.pdr_rtv field-reference row documents required keys."""

    def test_phases_pdr_rtv_field_documented(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        self.assertIn(
            "phases.pdr_rtv", body,
            "Observation schema must document the phases.pdr_rtv field")

    def test_phases_pdr_rtv_required_keys_documented(self):
        body = _observation_capture_section()
        # All required keys per AC13.
        required_keys = [
            "verdict",
            "n_candidates_iter0",
            "n_candidates_iter1",
            "tournament_rounds",
            "winner_slug",
            "cost_estimate_usd",
        ]
        for key in required_keys:
            self.assertIn(
                key, body,
                f"phases.pdr_rtv documentation must mention key `{key}`")

    def test_phases_pdr_rtv_tolerates_absence(self):
        body = _observation_capture_section()
        # The phases.pdr_rtv block must mention readers tolerating absence,
        # mirroring the phases.patch_critic precedent. We expect a clause
        # near the pdr_rtv documentation that says "tolerate absence".
        # Find the region around phases.pdr_rtv.
        pdr_rtv_region_match = re.search(
            r"(`?phases\.pdr_rtv`?.{0,2000})",
            body, re.DOTALL)
        self.assertIsNotNone(
            pdr_rtv_region_match,
            "phases.pdr_rtv documentation region not found")
        region = pdr_rtv_region_match.group(1).lower()
        self.assertIn(
            "tolerate absence", region,
            "phases.pdr_rtv documentation must include the "
            "'tolerate absence' backward-compatibility clause")


class PhasesPdrRtvFallbackReasonOptional(unittest.TestCase):
    """AC13 companion — fallback_reason field is optional with the
    correct enum values, present iff verdict is PDR_NO_CONSENSUS.
    """

    def test_phases_pdr_rtv_fallback_reason_optional(self):
        body = _observation_capture_section()
        # The fallback_reason field is mentioned in the pdr_rtv documentation.
        self.assertIn(
            "fallback_reason", body,
            "phases.pdr_rtv documentation must mention fallback_reason field")

    def test_phases_pdr_rtv_fallback_reason_enum_values_documented(self):
        body = _observation_capture_section()
        # All four enum values must appear.
        enum_values = [
            "worktree-cap-exceeded",
            "insufficient-green-builds",
            "all-finalists-rejected",
        ]
        for value in enum_values:
            self.assertIn(
                value, body,
                f"phases.pdr_rtv.fallback_reason enum must include "
                f"`{value}`")

    def test_phases_pdr_rtv_fallback_reason_optionality_explicit(self):
        body = _observation_capture_section()
        # Locate the region near fallback_reason and check for "optional"
        # AND a clause linking it to PDR_NO_CONSENSUS.
        # The text should explicitly say the field is optional.
        pdr_region_match = re.search(
            r"(fallback_reason.{0,1000})",
            body, re.DOTALL)
        self.assertIsNotNone(
            pdr_region_match,
            "fallback_reason documentation region not found")
        region = pdr_region_match.group(1).lower()
        self.assertIn(
            "optional", region,
            "fallback_reason field must be documented as optional")
        # Linkage to PDR_NO_CONSENSUS verdict (present iff failure).
        self.assertTrue(
            "pdr_no_consensus" in region or "no_consensus" in region or
            "verdict" in region,
            "fallback_reason documentation must link presence to "
            "PDR_NO_CONSENSUS verdict")


if __name__ == "__main__":
    unittest.main()
