"""Observation-length-cap hook tests (slice A onward).

Slice A authors the companion proposal doc + its keyword assertion.
Subsequent slices (D) add hook behaviour + settings.json wiring tests
into this file.
"""
import unittest
from pathlib import Path


class TestObservationLengthCapProposal(unittest.TestCase):
    """Slice A AC-A2: proposal doc exists and carries the load-bearing keywords."""

    def test_observation_length_cap_proposal_has_keywords(self):
        path = (Path(__file__).resolve().parents[1]
                / "protocols" / "_proposals"
                / "2026-05-14-observation-length-cap.md")
        self.assertTrue(path.exists(),
                        f"proposal missing: {path}")
        body = path.read_text()
        for keyword in ("would_truncate", "20%", "flip trigger", "50 events"):
            self.assertIn(keyword, body,
                          f"proposal body missing keyword: {keyword!r}")


if __name__ == "__main__":
    unittest.main()
