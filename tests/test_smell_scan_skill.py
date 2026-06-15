"""Tests for skills/smell-scan/SKILL.md — RED-first TDD (AC1-AC14).

AC1  SKILL.md exists + frontmatter parses (name, description, verdict, phase, dispatch, argument-hint)
AC2  phase == utility, dispatch == skill-tool
AC3  frontmatter verdict in {SMELLS_FOUND, SMELLS_CLEAN}; body names both verdicts
AC4  verdict-catalog has both info rows attributed to smell-scan emitter
AC5  skill-directory Active Skills has /harness:smell-scan row with both verdicts
AC6  README has `## Skills (70)` AND `# 70 skills` (count bump)
AC7  body names all 8 smell NAMES literally
AC8  Anti-Patterns section excludes shape-hook-owned smells (long function, long param, deep nesting)
AC9  advisory/never-blocks framing present
AC10 ranked table schema header present (file:line | smell | tier | why it matters | suggested refactor)
AC11 output-volume policy present (top-5 per tier cap; P3 suppression >10)
AC12 Shotgun Surgery + Divergent Change marked judgment-call/P3
AC13 source-file include/exclude list present; empty-after-filter -> SMELLS_CLEAN
AC14 code-reviewer named as canonical invoker
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = REPO_ROOT / "skills" / "smell-scan" / "SKILL.md"
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
SKILL_DIRECTORY = REPO_ROOT / "protocols" / "skill-directory.md"
README = REPO_ROOT / "README.md"


def _read_skill():
    return SKILL_MD.read_text()


def _parse_frontmatter(text):
    """Return dict of frontmatter key-value pairs."""
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm:
        return {}
    result = {}
    for line in fm.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"\'')
    return result


class AC1FrontmatterParseable(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(
            SKILL_MD.exists(),
            f"skills/smell-scan/SKILL.md must exist at {SKILL_MD}")

    def test_frontmatter_has_required_keys(self):
        text = _read_skill()
        fm = _parse_frontmatter(text)
        for key in ("name", "description", "verdict", "phase", "dispatch", "argument-hint"):
            self.assertIn(key, fm, f"frontmatter must contain key: {key}")

    def test_name_is_smell_scan(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(fm.get("name"), "smell-scan")

    def test_description_is_non_empty(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertTrue(fm.get("description"), "description must be non-empty")

    def test_argument_hint_is_non_empty(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertTrue(fm.get("argument-hint"), "argument-hint must be non-empty")


class AC2PhaseAndDispatch(unittest.TestCase):
    def test_phase_is_utility(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(
            fm.get("phase"), "utility",
            "phase must be 'utility'")

    def test_dispatch_is_skill_tool(self):
        fm = _parse_frontmatter(_read_skill())
        self.assertEqual(
            fm.get("dispatch"), "skill-tool",
            "dispatch must be 'skill-tool'")


class AC3VerdictsInFrontmatterAndBody(unittest.TestCase):
    def test_frontmatter_verdict_is_one_of_smells_verdicts(self):
        fm = _parse_frontmatter(_read_skill())
        verdict = fm.get("verdict", "")
        self.assertIn(
            verdict, ("SMELLS_FOUND", "SMELLS_CLEAN"),
            f"frontmatter verdict must be SMELLS_FOUND or SMELLS_CLEAN, got: {verdict!r}")

    def test_body_names_smells_found(self):
        text = _read_skill()
        self.assertIn("SMELLS_FOUND", text, "body must name verdict SMELLS_FOUND")

    def test_body_names_smells_clean(self):
        text = _read_skill()
        self.assertIn("SMELLS_CLEAN", text, "body must name verdict SMELLS_CLEAN")


class AC4VerdictCatalogRows(unittest.TestCase):
    def _catalog_text(self):
        return CATALOG.read_text()

    def test_smells_found_in_catalog(self):
        self.assertIn("`SMELLS_FOUND`", self._catalog_text(),
                      "SMELLS_FOUND must be in verdict-catalog.md")

    def test_smells_clean_in_catalog(self):
        self.assertIn("`SMELLS_CLEAN`", self._catalog_text(),
                      "SMELLS_CLEAN must be in verdict-catalog.md")

    def test_smells_found_has_info_polarity(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_FOUND" in line:
                self.assertIn("info", line,
                              "SMELLS_FOUND row must have polarity 'info'")
                break

    def test_smells_clean_has_info_polarity(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_CLEAN" in line:
                self.assertIn("info", line,
                              "SMELLS_CLEAN row must have polarity 'info'")
                break

    def test_smells_found_attributed_to_smell_scan(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_FOUND" in line:
                self.assertIn("smell-scan", line,
                              "SMELLS_FOUND row must attribute emitter 'smell-scan'")
                break

    def test_smells_clean_attributed_to_smell_scan(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_CLEAN" in line:
                self.assertIn("smell-scan", line,
                              "SMELLS_CLEAN row must attribute emitter 'smell-scan'")
                break

    def test_smells_found_phase_is_utility(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_FOUND" in line:
                self.assertIn("utility", line,
                              "SMELLS_FOUND row must have phase 'utility'")
                break

    def test_smells_clean_phase_is_utility(self):
        for line in self._catalog_text().splitlines():
            if "SMELLS_CLEAN" in line:
                self.assertIn("utility", line,
                              "SMELLS_CLEAN row must have phase 'utility'")
                break


class AC5SkillDirectoryRow(unittest.TestCase):
    def _active_skills_section(self):
        text = SKILL_DIRECTORY.read_text()
        match = re.search(
            r"##\s*Active Skills\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        return match.group(1) if match else ""

    def test_smell_scan_row_exists(self):
        section = self._active_skills_section()
        self.assertIn("/harness:smell-scan", section,
                      "skill-directory must have a /harness:smell-scan row")

    def test_smell_scan_row_has_smells_found(self):
        section = self._active_skills_section()
        row = None
        for line in section.splitlines():
            if "/harness:smell-scan" in line:
                row = line
                break
        self.assertIsNotNone(row, "/harness:smell-scan row not found")
        self.assertIn("SMELLS_FOUND", row,
                      "/harness:smell-scan row must mention SMELLS_FOUND")

    def test_smell_scan_row_has_smells_clean(self):
        section = self._active_skills_section()
        row = None
        for line in section.splitlines():
            if "/harness:smell-scan" in line:
                row = line
                break
        self.assertIsNotNone(row, "/harness:smell-scan row not found")
        self.assertIn("SMELLS_CLEAN", row,
                      "/harness:smell-scan row must mention SMELLS_CLEAN")


class AC6ReadmeCountBump(unittest.TestCase):
    def _readme(self):
        return README.read_text()

    def test_readme_has_skills_70_heading(self):
        self.assertRegex(
            self._readme(),
            r"(?m)^## Skills \(70\)$",
            "README must have `## Skills (70)` heading")

    def test_readme_has_70_skills_comment(self):
        self.assertRegex(
            self._readme(),
            r"#\s*70\s+skills",
            "README must have `# 70 skills` comment in architecture diagram")


class AC7SmellNamesInBody(unittest.TestCase):
    SMELL_NAMES = [
        "Feature Envy",
        "Data Clumps",
        "Primitive Obsession",
        "Message Chains",
        "Shotgun Surgery",
        "Divergent Change",
        "Middle Man",
        "Inappropriate Intimacy",
    ]

    def test_each_smell_name_present(self):
        text = _read_skill()
        for smell in self.SMELL_NAMES:
            self.assertIn(
                smell, text,
                f"SKILL.md body must name smell literally: {smell!r}")


class AC8AntiPatternsExcludesShapeHookSmells(unittest.TestCase):
    SHAPE_HOOK_SMELLS = [
        "long function",
        "long parameter list",
        "deep nesting",
    ]

    def test_anti_patterns_section_exists(self):
        text = _read_skill()
        self.assertIn("Anti-Patterns", text,
                      "SKILL.md must have an Anti-Patterns section")

    def test_shape_hook_smells_excluded(self):
        text = _read_skill().lower()
        for smell in self.SHAPE_HOOK_SMELLS:
            self.assertIn(
                smell.lower(), text,
                f"Anti-Patterns section must name and exclude shape-hook smell: {smell!r}")

    def test_out_label_present(self):
        text = _read_skill()
        # The body must explicitly say something is OUT for shape hooks
        self.assertRegex(
            text,
            r"(?i)out\b.*(shape|hook)",
            "Anti-Patterns section must label shape-hook smells as OUT")


class AC9AdvisoryFraming(unittest.TestCase):
    def test_advisory_word_present(self):
        text = _read_skill()
        self.assertIn("advisory", text.lower(),
                      "SKILL.md must contain advisory framing")

    def test_never_blocks_framing(self):
        text = _read_skill().lower()
        self.assertTrue(
            "never" in text and ("block" in text or "gate" in text),
            "SKILL.md must state it never blocks / never a gate")


class AC10RankedTableSchemaHeader(unittest.TestCase):
    REQUIRED_COLUMNS = [
        "file:line",
        "smell",
        "tier",
        "why it matters",
        "suggested refactor",
    ]

    def test_table_schema_header_present(self):
        text = _read_skill()
        for col in self.REQUIRED_COLUMNS:
            self.assertIn(
                col, text,
                f"SKILL.md ranked table schema must contain column: {col!r}")


class AC11OutputVolumePolicy(unittest.TestCase):
    def test_top_5_per_tier_cap_present(self):
        text = _read_skill()
        self.assertIn("5", text,
                      "SKILL.md must mention top-5 cap per tier")
        # Check for the per-tier cap concept
        self.assertRegex(
            text, r"(?i)(top.?5|cap.{0,20}5|5.{0,20}per.{0,10}tier)",
            "SKILL.md must specify top-5-per-tier cap")

    def test_p3_suppression_policy_present(self):
        text = _read_skill()
        self.assertIn("10", text,
                      "SKILL.md must mention suppression threshold of >10 P3")
        self.assertRegex(
            text, r"(?i)(suppress|noise.control)",
            "SKILL.md must mention P3 suppression for noise control")


class AC12ShotgunSurgeryDivergentChangeJudgmentCall(unittest.TestCase):
    def test_shotgun_surgery_marked_judgment_call(self):
        text = _read_skill()
        self.assertIn("Shotgun Surgery", text)
        # Find Shotgun Surgery context and check for judgment-call
        self.assertRegex(
            text, r"(?i)shotgun.{0,200}(judgment.call|P3|report.only)",
            "Shotgun Surgery must be marked judgment-call or P3 or report-only")

    def test_divergent_change_marked_judgment_call(self):
        text = _read_skill()
        self.assertIn("Divergent Change", text)
        self.assertRegex(
            text, r"(?i)divergent.{0,200}(judgment.call|P3|report.only)",
            "Divergent Change must be marked judgment-call or P3 or report-only")

    def test_shotgun_surgery_has_verify_manually_caveat(self):
        text = _read_skill()
        self.assertRegex(
            text, r"(?i)(verify.manually|judgment.call)",
            "Shotgun Surgery must carry 'verify manually' or 'judgment-call' caveat")

    def test_shotgun_surgery_fires_on_3_files_no_common_ancestor(self):
        text = _read_skill()
        self.assertRegex(
            text, r"(?i)(3|three).{0,50}(file|changed)",
            "Shotgun Surgery must define >=3 changed files threshold")


class AC13InputContractSourceFileScope(unittest.TestCase):
    INCLUDE_EXTENSIONS = [".ts", ".py", ".rb", ".go"]
    EXCLUDE_PATTERNS = ["*.md", "*.json", "*.yaml", "*.yml"]
    EXCLUDE_DIRS = ["spec/", "test/", "tests/", "__tests__/"]

    def test_include_extensions_present(self):
        text = _read_skill()
        for ext in self.INCLUDE_EXTENSIONS:
            self.assertIn(ext, text,
                          f"SKILL.md must list include extension {ext!r}")

    def test_exclude_md_present(self):
        text = _read_skill()
        self.assertIn("*.md", text,
                      "SKILL.md must exclude *.md files")

    def test_exclude_json_present(self):
        text = _read_skill()
        self.assertIn("*.json", text,
                      "SKILL.md must exclude *.json files")

    def test_exclude_yaml_present(self):
        text = _read_skill()
        self.assertTrue(
            "*.yaml" in text or "*.yml" in text,
            "SKILL.md must exclude *.yaml / *.yml files")

    def test_exclude_test_dirs_present(self):
        text = _read_skill()
        self.assertRegex(
            text, r"(?i)(test/|tests/|spec/|__tests__/)",
            "SKILL.md must exclude test directories")

    def test_empty_after_filter_smells_clean(self):
        text = _read_skill()
        self.assertRegex(
            text, r"(?i)(empty.{0,30}filter|0 source files|SMELLS_CLEAN.{0,30}0 source)",
            "SKILL.md must specify empty-after-filter -> SMELLS_CLEAN")


class AC14CodeReviewerNamedAsInvoker(unittest.TestCase):
    def test_code_reviewer_mentioned_as_invoker(self):
        text = _read_skill()
        self.assertIn("code-reviewer", text,
                      "SKILL.md must name code-reviewer as canonical invoker")

    def test_when_to_invoke_section_exists(self):
        text = _read_skill()
        self.assertIn("When to Invoke", text,
                      "SKILL.md must have a 'When to Invoke' section")

    def test_code_reviewer_mentioned_in_when_to_invoke(self):
        text = _read_skill()
        # Find the When to Invoke section
        match = re.search(
            r"##\s*When to Invoke\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md must have ## When to Invoke section")
        section = match.group(1)
        self.assertIn("code-reviewer", section,
                      "When to Invoke section must name code-reviewer as canonical invoker")


if __name__ == "__main__":
    unittest.main()
