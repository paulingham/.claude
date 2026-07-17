"""Iron Law 8 — Fail-closed gate design discipline.

Asserts that rules/safety.md (rules/core.md's Phase B gear-tier split target
for the universal-subset laws) carries Law 8 with:
  - Honest [ASPIRATIONAL] tag (not [ENFORCED])
  - Correct headline text ("A SECURITY OR CORRECTNESS GATE THAT CANNOT EVALUATE")
  - All five trigger conditions named
  - Two-test discipline clause with exact phrasing
  - Correct precedent pointers (is-protected-path.sh + agent-protocol.md)
  - No phantom hook citation
  - No misleading engineering-invariants.md § Security Baseline pointer

Also asserts:
  - protocols/work-class-routing.md updated to "Iron Laws (numbered 1-8)"
  - agents/architect.md DAG-validation line ("rules 1-7 against the architect") untouched

Hermetic: stdlib only (unittest, re, pathlib). No subprocess, no network,
no file writes, no process spawning.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _core_text() -> str:
    """Law 8 lives in rules/safety.md after the Phase B gear-tier split
    (rules/core.md is now a thin @-include index)."""
    return (REPO_ROOT / "rules" / "safety.md").read_text(encoding="utf-8")


def _routing_text() -> str:
    return (REPO_ROOT / "protocols" / "work-class-routing.md").read_text(encoding="utf-8")


def _architect_text() -> str:
    return (REPO_ROOT / "agents" / "architect.md").read_text(encoding="utf-8")


def _law8_block(text: str) -> str:
    """Extract the law-8 paragraph from core.md text."""
    match = re.search(r"(?m)^8\. \[ASPIRATIONAL\].*?(?=\n\n|\n##|\Z)", text, re.DOTALL)
    if match:
        return match.group(0)
    return ""


class IronLaw8Present(unittest.TestCase):
    """AC1 + AC2: Law 8 is present with correct tag and headline."""

    def setUp(self):
        self.text = _core_text()

    def test_ac1_headline_present(self):
        """AC1: headline regex matches the r2 law text."""
        pattern = r"(?m)^8\. \[ASPIRATIONAL\] \*\*A SECURITY OR CORRECTNESS GATE THAT CANNOT EVALUATE"
        self.assertRegex(
            self.text,
            pattern,
            "Law 8 headline not found in rules/core.md — expected "
            "'8. [ASPIRATIONAL] **A SECURITY OR CORRECTNESS GATE THAT CANNOT EVALUATE'",
        )

    def test_ac2_aspirational_tag(self):
        """AC2: Law 8 carries [ASPIRATIONAL], not [ENFORCED]."""
        pattern = r"(?m)^8\. \[ASPIRATIONAL\]"
        self.assertRegex(
            self.text,
            pattern,
            "Law 8 must carry [ASPIRATIONAL] tag",
        )
        not_enforced_pattern = r"(?m)^8\. \[ENFORCED\]"
        self.assertNotRegex(
            self.text,
            not_enforced_pattern,
            "Law 8 must NOT carry [ENFORCED] tag",
        )


class IronLaw8TriggerConditions(unittest.TestCase):
    """AC3: all five unevaluable-input triggers are named."""

    def setUp(self):
        self.text = _core_text()

    def test_ac3_trigger_empty_input(self):
        self.assertIn("empty input", self.text)

    def test_ac3_trigger_missing_file(self):
        self.assertIn("missing file", self.text)

    def test_ac3_trigger_unbound_variable(self):
        self.assertIn("unbound variable", self.text)

    def test_ac3_trigger_tool_error(self):
        self.assertIn("tool error", self.text)

    def test_ac3_trigger_absent_dependency(self):
        self.assertIn("absent dependency", self.text)


class IronLaw8TwoTestDiscipline(unittest.TestCase):
    """AC4: two-test discipline clause with exact phrasing."""

    def setUp(self):
        self.text = _core_text()

    def test_ac4_revert_red_clause(self):
        """AC4a: revert-RED clause present with exact wording."""
        self.assertIn(
            "goes RED when the gate's fail-closed line is reverted",
            self.text,
        )

    def test_ac4_unevaluable_input_clause(self):
        """AC4b: unevaluable-input clause present with exact wording."""
        self.assertIn(
            "feeds an unevaluable input and asserts the gate refuses",
            self.text,
        )


class IronLaw8HonestPointers(unittest.TestCase):
    """AC5: correct precedent pointers, no phantom hook, no misleading pointer."""

    def setUp(self):
        self.text = _core_text()
        self.block = _law8_block(self.text)

    def test_ac5_is_protected_path_pointer(self):
        """AC5: law-8 block references is-protected-path.sh."""
        self.assertIn(
            "is-protected-path.sh",
            self.block,
            "Law 8 must cite is-protected-path.sh as concrete precedent",
        )

    def test_ac5_agent_protocol_pointer(self):
        """AC5: law-8 block references protocols/agent-protocol.md."""
        self.assertIn(
            "protocols/agent-protocol.md",
            self.block,
            "Law 8 must cite protocols/agent-protocol.md",
        )

    def test_ac5_no_phantom_hook(self):
        """AC5: law-8 must NOT cite the invented fail-closed-guard.sh hook."""
        self.assertNotRegex(
            self.block,
            r"fail-closed-guard\.sh",
            "Law 8 must not cite a phantom 'fail-closed-guard.sh' hook",
        )

    def test_ac5_no_misleading_security_baseline_pointer(self):
        """AC5: law-8 must NOT point to engineering-invariants.md § Security Baseline."""
        self.assertNotIn(
            "engineering-invariants.md` § Security Baseline",
            self.block,
            "Law 8 must not cite 'engineering-invariants.md § Security Baseline' "
            "(misleading — that section covers SQLi/secrets, not fail-closed gates)",
        )


class IronLaw8RoutingCount(unittest.TestCase):
    """AC9: work-class-routing.md updated to 'Iron Laws (numbered 1-8)'."""

    def setUp(self):
        self.text = _routing_text()

    def test_ac9_routing_updated_to_1_8(self):
        """AC9: routing doc now says 'numbered 1-8'."""
        self.assertIn(
            "Iron Laws (numbered 1-8)",
            self.text,
            "work-class-routing.md must say 'Iron Laws (numbered 1-8)'",
        )

    def test_ac9_routing_old_count_absent(self):
        """AC9: old '1-7' count is gone from routing doc."""
        self.assertNotIn(
            "Iron Laws (numbered 1-7)",
            self.text,
            "work-class-routing.md must NOT still say 'Iron Laws (numbered 1-7)'",
        )


class IronLaw8ArchitectUntouched(unittest.TestCase):
    """AC10: agents/architect.md DAG-validation line was NOT collaterally edited."""

    def setUp(self):
        self.text = _architect_text()

    def test_ac10_dag_rules_line_preserved(self):
        """AC10: 'rules 1-7 against the architect' still present in architect.md."""
        self.assertIn(
            "rules 1-7 against the architect",
            self.text,
            "agents/architect.md DAG-validation line must not be collaterally edited",
        )


if __name__ == "__main__":
    unittest.main()
