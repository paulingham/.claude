"""C8 mutation-kill harness.

Runs a curated set of source-code mutations through the test suite and
asserts each mutation is killed by an existing test. Replaces the
external `mutmut`/`stryker` toolchain (not installed in this worktree)
with explicit perturbations on the load-bearing lines.

Each test below:
  1. Reads the original source file.
  2. Applies a single substring substitution that mutates a specific
     operator/constant.
  3. Spawns a fresh Python subprocess that runs the relevant unittest.
  4. Asserts the subprocess EXITS NON-ZERO (mutation killed).
  5. Restores the original source.

A subprocess is the only reliable way to defeat sys.modules caching
across many mutation-kill attempts in the same pytest session.
"""
import os
import subprocess
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "hooks" / "_lib"


@contextmanager
def _mutated_source(path, old, new):
    """Temporarily replace `old` with `new` in `path`. Restore on exit."""
    original = path.read_text()
    if old not in original:
        raise AssertionError(
            f"Mutation source string not found in {path}: {old!r}")
    path.write_text(original.replace(old, new, 1))
    try:
        yield
    finally:
        path.write_text(original)


def _run_tests(test_module_name, names):
    """Run named tests in a FRESH subprocess.

    Returns a CompletedProcess. Mutation is killed when returncode != 0.
    Subprocess isolation guarantees no sys.modules caching between
    consecutive mutation tests in the same pytest session.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{LIB}:{REPO_ROOT / 'tests'}:" + env.get("PYTHONPATH", ""))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    qualified = [f"{test_module_name}.{n}" for n in names]
    return subprocess.run(
        [sys.executable, "-m", "unittest", "-v"] + qualified,
        capture_output=True, text=True, env=env, timeout=60)


class MutationsAreKilled(unittest.TestCase):
    """Each test mutates one line and asserts at least one test fails."""

    def assertMutationKilled(self, result, mutation_label):
        """A mutation is killed when the subprocess returncode != 0."""
        self.assertNotEqual(
            result.returncode, 0,
            f"Mutation '{mutation_label}' SURVIVED — subprocess exited 0.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}")

    # ---------- S1: instinct_loader_helpers gate + category default ----

    def test_validate_category_gate_inversion_killed(self):
        """Inverting the category-gate condition (so unknown categories
        pass) MUST be killed by ValidateRejectsUnknownCategory."""
        path = LIB / "instinct_loader_helpers.py"
        old = 'fm["category"] not in _VALID_CATEGORIES'
        new = 'fm["category"] in _VALID_CATEGORIES'
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_loader_helpers", [
                "ValidateRejectsUnknownCategory."
                "test_unknown_category_returns_invalid_category_code",
            ])
        self.assertMutationKilled(result, "validate gate inversion")

    def test_normalize_category_default_changed_killed(self):
        """Changing the category default from "" to "x" MUST be killed
        by NormalizeDefaultsCategoryToEmptyString."""
        path = LIB / "instinct_loader_helpers.py"
        old = '"category": fm.get("category", "")'
        new = '"category": fm.get("category", "x")'
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_loader_helpers", [
                "NormalizeDefaultsCategoryToEmptyString."
                "test_absent_category_normalises_to_empty_string",
            ])
        self.assertMutationKilled(result, "category default empty-string")

    # ---------- S2: instinct_format AVOID prefix ----------------------

    def test_format_avoid_prefix_dropped_killed(self):
        """Removing the AVOID: prefix MUST be killed by
        RenderAntiPatternBulletPrefix."""
        path = LIB / "instinct_format.py"
        old = 'f"AVOID: {body}" if instinct.get("category") == "anti-pattern" else body'
        new = "body"
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_format", [
                "RenderAntiPatternBulletPrefix."
                "test_anti_pattern_bullet_starts_with_avoid",
            ])
        self.assertMutationKilled(result, "AVOID prefix removed")

    def test_format_anti_pattern_string_changed_killed(self):
        """Changing the literal "anti-pattern" string in the format
        comparator MUST be killed (no anti-pattern instinct ever
        matches → no AVOID prefix → tests fail)."""
        path = LIB / "instinct_format.py"
        old = '"anti-pattern" else body'
        new = '"anti-patternx" else body'
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_format", [
                "RenderAntiPatternBulletPrefix."
                "test_anti_pattern_bullet_starts_with_avoid",
            ])
        self.assertMutationKilled(result, "anti-pattern literal changed")

    # ---------- S3: instinct_injector boost --------------------------

    def test_injector_boost_amount_zeroed_killed(self):
        """Mutating `+0.1` to `+0.0` MUST be killed by
        weak-positive-dropped-when-antipattern-present."""
        path = LIB / "instinct_injector.py"
        old = 'i["confidence"] >= floor + 0.1'
        new = 'i["confidence"] >= floor + 0.0'
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_injector", [
                "AntiPatternFloorBoost."
                "test_weak_positive_dropped_when_antipattern_present",
            ])
        self.assertMutationKilled(result, "boost amount zeroed")

    def test_injector_anti_pattern_self_immunity_removed_killed(self):
        """Removing the self-immunity clause MUST be killed by
        test_antipattern_survives_when_its_confidence_below_boosted_floor."""
        path = LIB / "instinct_injector.py"
        old = ('after = [i for i in after if i.get("category") == "anti-pattern"\n'
               '                 or i["confidence"] >= floor + 0.1]')
        new = ('after = [i for i in after if i["confidence"] >= floor + 0.1]')
        with _mutated_source(path, old, new):
            result = _run_tests("test_instinct_injector", [
                "AntiPatternFloorBoost."
                "test_antipattern_survives_when_its_confidence_below_boosted_floor",
            ])
        self.assertMutationKilled(result, "self-immunity removed")

    # ---------- S4: mining gate + threshold + cap --------------------

    def test_mining_gate_off_by_one_killed(self):
        """Changing `rounds >= 2` to `rounds >= 1` MUST be killed by
        MiningGateRoundsLessThan2NoEmission."""
        path = LIB / "learn_anti_pattern_mining.py"
        old = "review_rounds is not None and review_rounds >= 2"
        new = "review_rounds >= 1"
        with _mutated_source(path, old, new):
            result = _run_tests("test_learn_anti_pattern_mining", [
                "MiningGateRoundsLessThan2NoEmission."
                "test_rounds_1_observations_produce_no_antipattern_files",
            ])
        self.assertMutationKilled(result, "rounds gate off-by-one")

    def test_mining_threshold_relaxed_to_2_killed(self):
        """Lowering `_RECURRENCE_THRESHOLD` from 3 to 2 MUST be
        killed by MiningRequiresThreeDistinctPipelines."""
        path = LIB / "learn_anti_pattern_mining.py"
        old = "_RECURRENCE_THRESHOLD = 3"
        new = "_RECURRENCE_THRESHOLD = 2"
        with _mutated_source(path, old, new):
            result = _run_tests("test_learn_anti_pattern_mining", [
                "MiningRequiresThreeDistinctPipelines."
                "test_third_recurrence_emits_first_and_second_do_not",
            ])
        self.assertMutationKilled(result, "recurrence threshold lowered")

    def test_mining_legacy_skipped_not_zero_killed(self):
        """Treating legacy `rounds is None` as a passing record MUST be
        killed by MiningSkipsLegacyObservationsWithoutRoundsField."""
        path = LIB / "learn_anti_pattern_mining.py"
        old = "review_rounds is not None and review_rounds >= 2"
        new = "(review_rounds or 2) >= 2"  # legacy None → 2 → pass gate
        with _mutated_source(path, old, new):
            result = _run_tests("test_learn_anti_pattern_mining", [
                "MiningSkipsLegacyObservationsWithoutRoundsField."
                "test_observations_missing_phases_review_rounds_key_skipped_not_zero",
            ])
        self.assertMutationKilled(result, "legacy-null coerced to passing")

    def test_mining_confidence_cap_lifted_killed(self):
        """Raising the cap from 0.85 to 1.0 MUST be killed by
        MiningConfidenceCappedAt085 (recurrence=20 → confidence > 0.85)."""
        path = LIB / "learn_anti_pattern_mining.py"
        old = "_CONFIDENCE_CAP = 0.85"
        new = "_CONFIDENCE_CAP = 1.0"
        with _mutated_source(path, old, new):
            result = _run_tests("test_learn_anti_pattern_mining", [
                "MiningConfidenceCappedAt085."
                "test_recurrence_20_yields_085_not_higher",
            ])
        self.assertMutationKilled(result, "confidence cap lifted")


if __name__ == "__main__":
    unittest.main()
