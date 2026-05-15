"""Slice D AC-D6 — flipped hook headers drop the "Path B, log-only" marker.

The hook file header is the in-code source of truth for whether a given
hook denies, mutates, or just logs. A header that says "log-only" when
the body emits `exit 2` is the canonical confusion vector (see plan
Pre-Mortem HIGH-3). Only `pre-agent-allowlist.sh` is currently flipped;
the other three retain their advisory header.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class FlippedHookHeadersDroppedPathB(unittest.TestCase):
    def test_allowlist_header_no_longer_says_log_only(self):
        body = (REPO_ROOT / "hooks" / "pre-agent-allowlist.sh").read_text()
        # Old characterisation removed
        self.assertNotIn("Path B, log-only", body)
        # New characterisation present
        self.assertIn("ENFORCING", body)
        # Promotion-criterion satisfied date breadcrumb
        self.assertIn("2026-05-14", body)


class AdvisoryHookHeadersUnchanged(unittest.TestCase):
    """The three mutation-semantic hooks keep their Path-B headers
    because they really are still advisory."""

    def test_thinking_header_still_path_b_log_only(self):
        body = (REPO_ROOT / "hooks" / "pre-agent-thinking.sh").read_text()
        self.assertIn("Path B, log-only", body)

    def test_advisor_header_still_path_b_log_only(self):
        body = (REPO_ROOT / "hooks" / "pre-agent-advisor.sh").read_text()
        self.assertIn("Path B, log-only", body)

    def test_instinct_header_still_path_b_log_only(self):
        body = (REPO_ROOT / "hooks" / "instinct-injector.sh").read_text()
        self.assertIn("Path B, log-only", body)


if __name__ == "__main__":
    unittest.main()
