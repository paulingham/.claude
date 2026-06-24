"""ATDD tests — A/B diff-economy + safety-retention eval mode (Slice 1).

AC1: ab subcommand documented in internal-eval SKILL.md + signature uses --arm-a/--arm-b flags
AC2: per-arm LOC delta + safety_pct computed from test pass rate; mutation surfaced when present
AC3: safety-first guard-return ladder (LOAD-BEARING: regression on safety drop even with LOC win)
AC4: ab-report discloses safety proxy + renders 4-state verdict copy verbatim
AC5: non-gating by design (no PreToolUse gate registered); regression verdict polarity is `info`;
     zero-scored-cases → INSUFFICIENT fail-closed (IL8 pair)
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INTERNAL_EVAL_SKILL = REPO_ROOT / "skills" / "internal-eval" / "SKILL.md"
SCORE_SKILL = REPO_ROOT / "skills" / "internal-eval" / "score" / "SKILL.md"
AB_COMPARE_PY = REPO_ROOT / "skills" / "internal-eval" / "score" / "lib" / "ab_compare.py"
VERDICT_CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
SKILL_DIRECTORY = REPO_ROOT / "protocols" / "skill-directory.md"


# ---------------------------------------------------------------------------
# AC1: ab subcommand documented + signature
# ---------------------------------------------------------------------------

class AC1AbSubcommandDocumented(unittest.TestCase):
    """ab must appear in internal-eval SKILL.md entry commands table."""

    def test_ab_subcommand_documented_runs_same_suite_twice(self):
        text = INTERNAL_EVAL_SKILL.read_text()
        self.assertIn("ab", text,
                      "internal-eval SKILL.md must document the `ab` subcommand")
        self.assertIn("--arm-a", text,
                      "internal-eval SKILL.md must document --arm-a flag")
        self.assertIn("--arm-b", text,
                      "internal-eval SKILL.md must document --arm-b flag")

    def test_ab_command_signature_passes_arm_ids_as_flags(self):
        text = INTERNAL_EVAL_SKILL.read_text()
        # Argument-hint must mention the ab subcommand with arm flags
        self.assertIn("ab --arm-a", text,
                      "argument-hint must include `ab --arm-a <run-id> --arm-b <run-id>`")

    def test_compare_arms_requires_both_arm_run_ids(self):
        """compare_arms() must raise or return INSUFFICIENT when arm ids missing (IL8)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("ab_compare", AB_COMPARE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Missing arm ids should fail-closed
        with self.assertRaises((ValueError, TypeError, SystemExit)):
            mod.compare_arms(scored_a=[], scored_b=[])


# ---------------------------------------------------------------------------
# AC2: per-arm metric computation
# ---------------------------------------------------------------------------

class AC2PerArmMetricComputation(unittest.TestCase):
    """LOC delta from candidate diffs; safety_pct from test pass rate."""

    def _load_ab_compare(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ab_compare", AB_COMPARE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_per_arm_loc_delta_computed_from_candidate_diff(self):
        mod = self._load_ab_compare()
        result = mod.compare_arms(
            arm_a_run_id="run-a", arm_b_run_id="run-b",
            scored_a=[{"pass": True, "loc_added": 10, "loc_removed": 2}],
            scored_b=[{"pass": True, "loc_added": 5, "loc_removed": 2}],
        )
        # net LOC: A=+8, B=+3 → arm B has fewer LOC
        self.assertIn("loc_a", result)
        self.assertIn("loc_b", result)
        self.assertLess(result["loc_b"], result["loc_a"],
                        "arm B has fewer net LOC than arm A")

    def test_per_arm_safety_pct_from_test_pass_rate(self):
        mod = self._load_ab_compare()
        result = mod.compare_arms(
            arm_a_run_id="run-a", arm_b_run_id="run-b",
            scored_a=[{"pass": True}, {"pass": True}, {"pass": False}],
            scored_b=[{"pass": True}, {"pass": True}, {"pass": True}],
        )
        # arm A: 2/3 pass = 0.667; arm B: 3/3 = 1.0
        self.assertAlmostEqual(result["safety_a"], 2 / 3, places=3)
        self.assertAlmostEqual(result["safety_b"], 1.0, places=3)

    def test_safety_pct_degrades_gracefully_when_mutation_absent(self):
        """When no mutation artifact, safety_pct still returns a finite float."""
        mod = self._load_ab_compare()
        result = mod.compare_arms(
            arm_a_run_id="run-a", arm_b_run_id="run-b",
            scored_a=[{"pass": True}], scored_b=[{"pass": True}],
            mutation_score_a=None, mutation_score_b=None,
        )
        self.assertIsInstance(result["safety_a"], float)
        self.assertIsInstance(result["safety_b"], float)
        self.assertFalse(
            result["safety_a"] != result["safety_a"],  # NaN check
            "safety_a must not be NaN when mutation absent")


# ---------------------------------------------------------------------------
# AC3: safety-first guard-return ladder (LOAD-BEARING)
# ---------------------------------------------------------------------------

class AC3SafetyFirstLadder(unittest.TestCase):
    """Ladder is a guard-return structure; regression branch physically unreachable
    when safety floor holds."""

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ab_compare", AB_COMPARE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_safety_drop_forces_regression_even_with_huge_loc_win(self):
        """LOAD-BEARING: arm B has massive LOC reduction but safety dropped."""
        mod = self._load()
        scored_a = [{"pass": True, "loc_added": 100, "loc_removed": 0}] * 10
        scored_b = ([{"pass": True, "loc_added": 1, "loc_removed": 0}] * 8 +
                    [{"pass": False, "loc_added": 1, "loc_removed": 0}] * 2)
        result = mod.compare_arms(arm_a_run_id="run-a", arm_b_run_id="run-b",
                                  scored_a=scored_a, scored_b=scored_b)
        self.assertEqual(result["verdict"], "EVAL_REGRESSION_DETECTED",
                         "safety drop must force EVAL_REGRESSION_DETECTED even with LOC win")

    def test_loc_reduction_with_safety_held_confirms_improvement(self):
        mod = self._load()
        scored_a = [{"pass": True, "loc_added": 10, "loc_removed": 0}] * 5
        scored_b = [{"pass": True, "loc_added": 3, "loc_removed": 0}] * 5
        result = mod.compare_arms(arm_a_run_id="run-a", arm_b_run_id="run-b",
                                  scored_a=scored_a, scored_b=scored_b)
        self.assertEqual(result["verdict"], "EVAL_IMPROVEMENT_CONFIRMED",
                         "LOC reduction with safety held must confirm improvement")

    def test_no_significant_diff_economy_change_is_neutral(self):
        mod = self._load()
        scored = [{"pass": True, "loc_added": 5, "loc_removed": 0}] * 5
        result = mod.compare_arms(arm_a_run_id="run-a", arm_b_run_id="run-b",
                                  scored_a=scored, scored_b=scored)
        self.assertEqual(result["verdict"], "EVAL_NEUTRAL",
                         "no significant diff-economy change must be EVAL_NEUTRAL")

    def test_epsilon_safety_default_is_tight(self):
        mod = self._load()
        self.assertLessEqual(
            mod.EPSILON_SAFETY_DEFAULT, 0.02,
            "EPSILON_SAFETY_DEFAULT must be <= 0.02 to enforce tight floor")

    def test_three_verdicts_registered_in_catalog_and_directory(self):
        catalog_text = VERDICT_CATALOG.read_text()
        directory_text = SKILL_DIRECTORY.read_text()
        for verdict in ("EVAL_IMPROVEMENT_CONFIRMED", "EVAL_REGRESSION_DETECTED",
                        "EVAL_NEUTRAL"):
            self.assertIn(verdict, catalog_text,
                          f"{verdict} must be registered in verdict-catalog.md")
            self.assertIn(verdict, directory_text,
                          f"{verdict} must be in skill-directory.md internal-eval row")


# ---------------------------------------------------------------------------
# AC4: ab-report structure
# ---------------------------------------------------------------------------

class AC4AbReportStructure(unittest.TestCase):
    """ab-report.md must disclose safety proxy and render verdict copy."""

    def test_ab_report_discloses_safety_proxy_per_arm(self):
        score_skill_text = SCORE_SKILL.read_text()
        self.assertIn("proxy", score_skill_text.lower(),
                      "score/SKILL.md must document safety proxy disclosure")
        self.assertIn("Safety proxy", score_skill_text,
                      "score/SKILL.md must name the `Safety proxy:` line")

    def test_ab_report_renders_four_state_verdict_copy(self):
        internal_eval_text = INTERNAL_EVAL_SKILL.read_text()
        # All four verdict states must have copy in the SKILL.md
        for marker in ("EVAL_IMPROVEMENT_CONFIRMED", "EVAL_REGRESSION_DETECTED",
                       "EVAL_NEUTRAL", "INSUFFICIENT"):
            self.assertIn(marker, internal_eval_text,
                          f"internal-eval SKILL.md must include {marker} verdict copy")


# ---------------------------------------------------------------------------
# AC5: non-gating, info polarity, IL8 fail-closed
# ---------------------------------------------------------------------------

class AC5NonGatingAndFailClosed(unittest.TestCase):
    """ab mode never registers a PreToolUse gate; regression polarity is info."""

    def test_ab_mode_registers_no_pretooluse_gate(self):
        """ab-compare.sh must not appear as a PreToolUse matcher in hooks."""
        hooks_json = REPO_ROOT / "hooks" / "hooks.json"
        settings_json = REPO_ROOT / "settings.json"
        for config_path in (hooks_json, settings_json):
            if not config_path.exists():
                continue
            text = config_path.read_text()
            self.assertNotIn(
                "ab-compare",
                text,
                f"ab-compare must not register a PreToolUse gate in {config_path.name}",
            )

    def test_regression_verdict_polarity_is_info_not_failure(self):
        catalog_text = VERDICT_CATALOG.read_text()
        # Find the EVAL_REGRESSION_DETECTED row and verify polarity is info
        pattern = re.compile(
            r"^\|\s*`EVAL_REGRESSION_DETECTED`\s*\|\s*([a-z]+)\s*\|",
            re.MULTILINE)
        m = pattern.search(catalog_text)
        self.assertIsNotNone(m, "EVAL_REGRESSION_DETECTED must be in verdict-catalog.md")
        self.assertEqual(m.group(1), "info",
                         "EVAL_REGRESSION_DETECTED polarity must be `info` not `failure`")

    def test_zero_scored_cases_fail_closed_line_is_exercised(self):
        """IL8 pair (a): the zero-cases guard line is present in ab_compare.py source."""
        source = AB_COMPARE_PY.read_text()
        # The guard must return INSUFFICIENT for zero scored cases
        self.assertIn("INSUFFICIENT", source,
                      "ab_compare.py must have INSUFFICIENT guard for zero cases")
        # The guard must structurally precede the safety/improvement branches
        insufficient_pos = source.index("INSUFFICIENT")
        # Safety floor logic must come AFTER the INSUFFICIENT guard
        regression_pos = source.find("REGRESSION")
        self.assertLess(insufficient_pos, regression_pos,
                        "INSUFFICIENT guard must appear before REGRESSION branch in source")

    def test_zero_scored_cases_refuses_with_insufficient(self):
        """IL8 pair (b): calling compare_arms with 0 scored cases returns INSUFFICIENT."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("ab_compare", AB_COMPARE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.compare_arms(arm_a_run_id="run-a", arm_b_run_id="run-b",
                                  scored_a=[], scored_b=[])
        self.assertEqual(result["verdict"], "INSUFFICIENT",
                         "zero scored cases must return INSUFFICIENT, not 100% pass")
        # Must carry case counts, not silent
        self.assertIn("n_a", result)
        self.assertIn("n_b", result)
