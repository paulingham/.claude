"""Best-of-N gate predicate tests (incremental TDD)."""
import unittest

from bestofn_gate import should_dispatch_bestofn


class CriticalEnables(unittest.TestCase):
    # Intentional behavior change post-C2 fan-out cap audit (PR #c2-fanout-cap-audit):
    # tier-gated predicate requires tier='T6' AND budget>=7. critical=True alone
    # no longer enables Best-of-N; the old assertion (assertTrue) is wrong.
    def test_critical_bug_low_budget_enables(self):
        self.assertFalse(should_dispatch_bestofn(True, "bug", 2))

    def test_critical_feature_enables(self):
        self.assertFalse(should_dispatch_bestofn(True, "feature", 5))


class NonCriticalFeatureDisables(unittest.TestCase):
    def test_feature_budget_5_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "feature", 5))

    def test_feature_high_budget_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "feature", 12))


class NonCriticalOtherClassesDisable(unittest.TestCase):
    def test_bug_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "bug", 8))

    def test_refactor_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "refactor", 10))

    def test_spike_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "spike", 12))

    def test_empty_class_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "", 9))


class UserOverrideEnables(unittest.TestCase):
    def test_token_in_request_enables(self):
        self.assertTrue(
            should_dispatch_bestofn(False, "feature", 2, "Add login [best-of-n]")
        )

    def test_token_case_insensitive(self):
        self.assertTrue(
            should_dispatch_bestofn(False, "bug", 1, "Fix bug [BEST-OF-N]")
        )

    def test_token_alone_enables(self):
        self.assertTrue(should_dispatch_bestofn(False, "refactor", 3, "[best-of-n]"))


class NoOverrideTokenDisables(unittest.TestCase):
    def test_partial_token_disables(self):
        self.assertFalse(
            should_dispatch_bestofn(False, "feature", 5, "best of n please")
        )

    def test_empty_request_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "feature", 5, ""))


class TierBudgetGating(unittest.TestCase):
    """RED stubs for AC1: gear+budget gate enforcement."""

    def test_build_critical_high_budget_disables(self):
        # BUILD + critical + budget=10: must return False (gear gate blocks it)
        self.assertFalse(
            should_dispatch_bestofn(True, "feature", 10, "", gear="BUILD")
        )

    def test_pipeline_critical_budget6_disables(self):
        # PIPELINE + critical + budget=6: must return False (budget<7 gate blocks it)
        self.assertFalse(
            should_dispatch_bestofn(True, "feature", 6, "", gear="PIPELINE")
        )

    def test_pipeline_critical_budget7_enables(self):
        # PIPELINE + critical + budget=7: happy path — all gates pass
        self.assertTrue(
            should_dispatch_bestofn(True, "feature", 7, "", gear="PIPELINE")
        )

    def test_override_bypasses_gear_gate_at_build(self):
        # [best-of-n] override must bypass gear+budget gate entirely
        self.assertTrue(
            should_dispatch_bestofn(False, "bug", 2, "[best-of-n]", gear="BUILD")
        )

    def test_pipeline_budget7_non_critical_disables(self):
        # PIPELINE + budget=7 + critical=False: must return False (critical clause)
        self.assertFalse(
            should_dispatch_bestofn(False, "feature", 7, "", gear="PIPELINE")
        )


class GearValueMirrorsLegacyTierT6(unittest.TestCase):
    """Gear-value happy path mirroring the retired tier=='T6' behaviour exactly."""

    def test_gear_pipeline_critical_budget7_enables(self):
        self.assertTrue(
            should_dispatch_bestofn(True, "feature", 7, "", gear="PIPELINE")
        )

    def test_gear_build_critical_budget7_disables(self):
        self.assertFalse(
            should_dispatch_bestofn(True, "feature", 7, "", gear="BUILD")
        )

    def test_gear_pair_critical_budget7_disables(self):
        self.assertFalse(
            should_dispatch_bestofn(True, "feature", 7, "", gear="PAIR")
        )


if __name__ == "__main__":
    unittest.main()
