"""Tests for skills/debt-ledger/SKILL.md — AC3 (skill contract) + AC4 (wire-in).

AC3  SKILL.md exists + frontmatter parses (name, description, verdict, phase, dispatch, argument-hint)
     phase == utility, dispatch == skill-tool
     BOTH verdicts named: DEBT_LEDGER_WRITTEN + DEBT_LEDGER_CLEAN; advisory / never-blocks framing
     no-trigger rot concept present; exclusion dirs named; empty-tree -> DEBT_LEDGER_CLEAN
AC4  verdict-catalog has BOTH rows (info polarity, emitter debt-ledger, phase utility)
     skill-directory Active Skills has /harness:debt-ledger row with both verdicts
     README skill count == 73
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = REPO_ROOT / "skills" / "debt-ledger" / "SKILL.md"
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
SKILL_DIRECTORY = REPO_ROOT / "protocols" / "skill-directory.md"
README = REPO_ROOT / "README.md"


def _read_skill():
    return SKILL_MD.read_text()


def _parse_frontmatter(text):
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm:
        return {}
    result = {}
    for line in fm.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"\'')
    return result


class AC3FrontmatterParseable(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(
            SKILL_MD.exists(),
            f"skills/debt-ledger/SKILL.md must exist at {SKILL_MD}")

    def test_frontmatter_has_required_keys(self):
        fm = _parse_frontmatter(_read_skill())
        for key in ("name", "description", "verdict", "phase", "dispatch", "argument-hint"):
            self.assertIn(key, fm, f"frontmatter must contain key: {key}")

    def test_name_is_debt_ledger(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(fm.get("name"), "debt-ledger")

    def test_description_non_empty(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertTrue(fm.get("description"), "description must be non-empty")

    def test_argument_hint_non_empty(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertTrue(fm.get("argument-hint"), "argument-hint must be non-empty")


class AC3PhaseAndDispatch(unittest.TestCase):
    def test_phase_is_utility(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(fm.get("phase"), "utility", "phase must be 'utility'")

    def test_dispatch_is_skill_tool(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(fm.get("dispatch"), "skill-tool", "dispatch must be 'skill-tool'")


class AC3VerdictsInFrontmatterAndBody(unittest.TestCase):
    def test_frontmatter_verdict_is_a_debt_verdict(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertIn(
            fm.get("verdict", ""), ("DEBT_LEDGER_WRITTEN", "DEBT_LEDGER_CLEAN"),
            "frontmatter verdict must be DEBT_LEDGER_WRITTEN or DEBT_LEDGER_CLEAN")

    def test_body_names_debt_ledger_written(self):
        self.assertIn("DEBT_LEDGER_WRITTEN", _read_skill(),
                      "body must name verdict DEBT_LEDGER_WRITTEN")

    def test_body_names_debt_ledger_clean(self):
        self.assertIn("DEBT_LEDGER_CLEAN", _read_skill(),
                      "body must name verdict DEBT_LEDGER_CLEAN")


class AC3AdvisoryFraming(unittest.TestCase):
    def test_advisory_word_present(self):
        self.assertIn("advisory", _read_skill().lower(),
                      "SKILL.md must contain advisory framing")

    def test_never_blocks_framing(self):
        text = _read_skill().lower()
        self.assertTrue(
            "never" in text and ("block" in text or "gate" in text),
            "SKILL.md must state it never blocks / never a gate")


class AC3NoTriggerRot(unittest.TestCase):
    def test_no_trigger_concept_present(self):
        text = _read_skill().lower()
        self.assertIn("no-trigger", text,
                      "SKILL.md must define the `no-trigger` rot flag")

    def test_silent_rot_named(self):
        self.assertIn("rot", _read_skill().lower(),
                      "SKILL.md must describe no-trigger entries as rot")

    def test_second_clause_definition(self):
        text = _read_skill().lower()
        self.assertRegex(
            text, r"(second clause|no comma|upgrade.?trigger)",
            "SKILL.md must define no-trigger as a missing second clause / upgrade-trigger")


class AC3ExclusionDirs(unittest.TestCase):
    EXCLUDED = ["node_modules", ".git", "dist", "build", "target", ".claude/worktrees"]

    def test_exclusion_dirs_named(self):
        text = _read_skill()
        for d in self.EXCLUDED:
            self.assertIn(d, text, f"SKILL.md must name excluded dir: {d!r}")

    def test_grep_pattern_present(self):
        text = _read_skill()
        self.assertIn("DEBT:", text, "SKILL.md must show the DEBT: grep pattern")


class AC3EmptyTreePath(unittest.TestCase):
    def test_empty_tree_emits_clean(self):
        text = _read_skill()
        self.assertRegex(
            text, r"(?i)(no DEBT markers found|zero DEBT|DEBT_LEDGER_CLEAN)",
            "SKILL.md must document the empty-tree -> DEBT_LEDGER_CLEAN path")


class AC3CadenceNote(unittest.TestCase):
    def test_recommended_cadence_present(self):
        text = _read_skill().lower()
        self.assertRegex(
            text, r"(cadence|periodic|at reflect|over time)",
            "SKILL.md must carry a recommended-cadence discoverability note")


class AC4VerdictCatalogRows(unittest.TestCase):
    def _catalog(self):
        return CATALOG.read_text()

    def _row(self, verdict):
        for line in self._catalog().splitlines():
            if verdict in line:
                return line
        return None

    def test_written_in_catalog(self):
        self.assertIn("`DEBT_LEDGER_WRITTEN`", self._catalog())

    def test_clean_in_catalog(self):
        self.assertIn("`DEBT_LEDGER_CLEAN`", self._catalog())

    def test_written_info_emitter_phase(self):
        row = self._row("DEBT_LEDGER_WRITTEN")
        self.assertIsNotNone(row)
        self.assertIn("info", row)
        self.assertIn("debt-ledger", row)
        self.assertIn("utility", row)

    def test_clean_info_emitter_phase(self):
        row = self._row("DEBT_LEDGER_CLEAN")
        self.assertIsNotNone(row)
        self.assertIn("info", row)
        self.assertIn("debt-ledger", row)
        self.assertIn("utility", row)


class AC4SkillDirectoryRow(unittest.TestCase):
    def _active_skills_section(self):
        text = SKILL_DIRECTORY.read_text()
        match = re.search(r"##\s*Active Skills\s*\n(.+?)(?=\n##\s|\Z)", text, re.DOTALL)
        return match.group(1) if match else ""

    def _row(self):
        for line in self._active_skills_section().splitlines():
            if "/harness:debt-ledger" in line:
                return line
        return None

    def test_row_exists(self):
        self.assertIn("/harness:debt-ledger", self._active_skills_section())

    def test_row_has_written(self):
        self.assertIn("DEBT_LEDGER_WRITTEN", self._row())

    def test_row_has_clean(self):
        self.assertIn("DEBT_LEDGER_CLEAN", self._row())


class AC4ReadmeCount(unittest.TestCase):
    def _readme(self):
        return README.read_text()

    def test_readme_skills_72_heading(self):
        self.assertRegex(self._readme(), r"(?m)^## Skills \(74\)$",
                         "README must have `## Skills (74)` heading")

    def test_readme_72_skills_comment(self):
        self.assertRegex(self._readme(), r"#\s*74\s+skills",
                         "README must have `# 74 skills` comment")


if __name__ == "__main__":
    unittest.main()
