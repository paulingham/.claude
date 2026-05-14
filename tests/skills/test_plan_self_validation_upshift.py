"""Slice B — AC7 (state-file routing fields + rules/core.md upshift fixture)
Tests:
  - test_state_file_carries_routing_fields: parses SKILL.md state template and
    asserts the YAML keys tier_initial/tier_replanned/routing_upshifted are
    present in the template block.
  - test_rules_core_md_path_triggers_t6_upshift: simulated fixture plan with
    ## Affected Files listing rules/core.md → tier_replanned should be T6
    (documented per HIGH-1).
"""
import os
import re
import subprocess
import unittest

REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"]
).decode().strip()
PSV_SKILL = os.path.join(REPO_ROOT, "skills", "plan-self-validation", "SKILL.md")


def _read():
    with open(PSV_SKILL, "r", encoding="utf-8") as f:
        return f.read()


class PlanSelfValidationUpshiftTest(unittest.TestCase):
    def test_state_file_carries_routing_fields(self):
        text = _read()
        for key in ("tier_initial", "tier_replanned", "routing_upshifted"):
            self.assertRegex(text, rf"(?m)^\s*{key}\s*:", f"missing key: {key}")

    def test_rules_core_md_path_triggers_t6_upshift(self):
        text = _read()
        # The Step 0 documentation must explicitly state that touching
        # rules/core.md upshifts to T6 (conservative safety override).
        # Pattern: explicit mention of rules/core.md as upshift trigger AND T6
        self.assertRegex(text, r"rules/core\.md")
        self.assertRegex(text, r"T6")

    def test_verdict_enum_extended(self):
        text = _read()
        # Verdict enum line must include ROUTING_UPSHIFTED
        self.assertRegex(text, r"PLAN_APPROVED\s*\|\s*PLAN_HOLES\s*\|\s*ROUTING_UPSHIFTED")

    def test_routing_upshifted_monotonic(self):
        text = _read()
        # Memory M10 / R3 — upshift is monotonic-once; Step 0 must document this.
        # Acceptable phrasing: "monotonic-once" or "upshift-once" or
        # equivalent invariant statement.
        self.assertRegex(
            text,
            r"monotonic|once|upshift.{0,40}once",
        )


if __name__ == "__main__":
    unittest.main()
