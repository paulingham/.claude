"""AC6 + AC7 + AC13 — patch-critic rubric § 5 lists 6 assertions; Inputs
section does not visually inspect screenshots; index-absent vs
mcp-unavailable produce different operator output.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_CRITIC = REPO_ROOT / "agents" / "patch-critic.md"
PATCH_CRITIQUE_SKILL = REPO_ROOT / "skills" / "patch-critique" / "SKILL.md"


def _section(text, name):
    pat = re.compile(
        rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1) if m else ""


class PatchCriticRubricSection5(unittest.TestCase):
    """AC6 — § 5 contains all six assertion IDs verbatim."""

    def test_patch_critic_rubric_section_5_lists_six_assertions(self):
        text = PATCH_CRITIC.read_text()
        # Confirm a § 5 (heading-level "5." or "Rubric § 5" or
        # explicit a11y rubric header) exists.
        self.assertRegex(text, r"(§\s*5|^###?\s*5\.)", )
        for aid in ("A1", "A2", "A3", "A4", "A5", "A6"):
            self.assertIn(aid, text, f"missing assertion id {aid}")


class PatchCriticInputsForbidVisualInspection(unittest.TestCase):
    """AC7 — Inputs section MUST NOT mention visual review of screenshots."""

    def test_patch_critic_inputs_do_not_mention_visual_inspection(self):
        text = PATCH_CRITIC.read_text()
        inputs = _section(text, "Inputs")
        for forbidden in (r"\bscreenshot",
                          r"visual judgement",
                          r"visual review",
                          r"\bJPEG\b"):
            self.assertNotRegex(
                inputs, re.compile(forbidden, re.IGNORECASE),
                f"Inputs section contains forbidden phrase {forbidden!r}: "
                f"{inputs!r}")


class IndexAbsentVsMcpUnavailable(unittest.TestCase):
    """AC13 — index-absent silent SKIP vs mcp-unavailable remediation row."""

    def test_patch_critic_documents_index_absent_silent_skip(self):
        text = PATCH_CRITIC.read_text()
        # § 5 must state index-absent => no row rendered.
        self.assertRegex(
            text, r"index[- ]absent.*(?:omitted|silent\s*SKIP|no\s*§\s*5)",
            "patch-critic must document the index-absent silent SKIP "
            "behavior (no § 5 row)")

    def test_patch_critic_documents_mcp_unavailable_remediation(self):
        text = PATCH_CRITIC.read_text()
        # Must contain remediation pointer for mcp-unavailable case.
        self.assertIn("mcp-unavailable", text)
        self.assertRegex(
            text, r"Remediation|remediation",
            "patch-critic must include remediation text for mcp-unavailable")


if __name__ == "__main__":
    unittest.main()
