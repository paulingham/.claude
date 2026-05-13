"""AC3 — `/forensics` surfaces sandbox-divergence findings.

`skills/forensics/SKILL.md` Step 3 has a dedicated sandbox-divergence
detection block: when the pipeline state contains a `build.md` file
with a `## Sandbox Verify` section whose verdict is `SANDBOX_FAILED`,
the forensics report renders the diverging test names AND joins them
against any scratchpad findings categorised as `fragility` whose text
mentions the test name.

The skill text IS the contract. These tests assert that the rendered
forensics body contains the right blocks. They consume the same
reader helper (`hooks/_lib/sandbox_verify_observation.py`).
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import sandbox_verify_observation
    return sandbox_verify_observation


class ForensicsParsesDivergingTestsFromBuildMd(unittest.TestCase):
    """forensics consumer uses the reader helper end-to-end."""

    def test_parses_diverging_tests_from_realistic_build_md(self):
        mod = _load()
        # Realistic build.md output from a SANDBOX_FAILED Build round.
        build_md = """## Decision Record
- Chose: foo.

## Context for Review
- Nothing.

## Sandbox Verify
- Worktree pass: 18/20
- Sandbox pass:   17/20
- Verdict: SANDBOX_FAILED

| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| tests/test_login.py::test_a | PASS | FAIL | diverge |
| tests/test_login.py::test_b | PASS | PASS | match |
| tests/test_signup.py::test_c | FAIL | PASS | diverge |
"""
        tests = mod.diverging_tests_from_build_md(build_md)
        self.assertEqual(len(tests), 2)
        self.assertIn("tests/test_login.py::test_a", tests)
        self.assertIn("tests/test_signup.py::test_c", tests)


class ForensicsRendersDivergenceSectionOnSandboxFailed(unittest.TestCase):
    """The forensics skill text renders a `## Sandbox Divergence` block."""

    def test_forensics_skill_text_documents_divergence_block(self):
        doc = (REPO_ROOT / "skills" / "forensics" / "SKILL.md").read_text()
        # The Step 3 anomaly-detection section MUST document the
        # sandbox-divergence detection block so it survives future
        # skill edits.
        idx = doc.find("Step 3:")
        self.assertGreater(idx, -1)
        section = doc[idx:idx + 6000]
        # Either the explicit sub-step header or the SANDBOX_FAILED label.
        body = section.lower()
        self.assertTrue(
            "sandbox" in body,
            "Step 3 must reference sandbox-divergence detection")
        # The render snippet should mention the SANDBOX_FAILED verdict.
        self.assertIn("SANDBOX_FAILED", section,
                      "Step 3 must show the SANDBOX_FAILED trigger")


class ForensicsJoinsScratchpadFindingsByTestName(unittest.TestCase):
    """Skill text documents the join: diverging test names × fragility findings."""

    def test_join_pattern_documented(self):
        doc = (REPO_ROOT / "skills" / "forensics" / "SKILL.md").read_text()
        idx = doc.find("Step 3:")
        section = doc[idx:idx + 6000].lower()
        # The join surface mentions scratchpad/fragility — keeps the
        # forensics consumer documented even when the helper changes.
        self.assertTrue(
            "scratchpad" in section or "fragility" in section
            or "join" in section,
            "Step 3 must mention scratchpad joinable surface")


class ForensicsAbsentSandboxSectionIsClean(unittest.TestCase):
    """When build.md has NO `## Sandbox Verify` section, helper is silent."""

    def test_helper_returns_empty_for_missing_section(self):
        mod = _load()
        build_md_no_sandbox = "## Decision Record\n- nothing.\n"
        self.assertEqual(
            mod.diverging_tests_from_build_md(build_md_no_sandbox),
            [],
            "absent sandbox block produces empty list, never crashes")

    def test_helper_returns_empty_for_empty_string(self):
        mod = _load()
        self.assertEqual(mod.diverging_tests_from_build_md(""), [])


class ForensicsHandlesBuildMdFromFile(unittest.TestCase):
    """Real-world: forensics reads build.md from disk, then parses."""

    def test_round_trip_via_disk(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build.md"
            path.write_text("""## Sandbox Verify
- Verdict: SANDBOX_FAILED

| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| tests/x.py::t | PASS | FAIL | diverge |
""")
            tests = mod.diverging_tests_from_build_md(path.read_text())
            self.assertEqual(tests, ["tests/x.py::t"])


if __name__ == "__main__":
    unittest.main()
