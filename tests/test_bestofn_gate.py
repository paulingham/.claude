"""Best-of-N gate predicate tests (incremental TDD)."""
import unittest

from bestofn_gate import should_dispatch_bestofn


class FeatureAtThresholdEnables(unittest.TestCase):
    def test_feature_budget_5_enables(self):
        self.assertTrue(should_dispatch_bestofn(False, "feature", 5))


class FeatureBelowThresholdDisables(unittest.TestCase):
    def test_feature_budget_4_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "feature", 4))


class BugWithHighBudgetDisables(unittest.TestCase):
    def test_bug_budget_8_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "bug", 8))


class RefactorWithHighBudgetDisables(unittest.TestCase):
    def test_refactor_budget_10_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "refactor", 10))


class SpikeWithHighBudgetDisables(unittest.TestCase):
    def test_spike_budget_12_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "spike", 12))


class CriticalBugLowBudgetEnables(unittest.TestCase):
    def test_critical_bug_low_budget_enables(self):
        self.assertTrue(should_dispatch_bestofn(True, "bug", 2))


class CriticalFeatureAtThresholdEnables(unittest.TestCase):
    def test_critical_feature_budget_5_enables(self):
        self.assertTrue(should_dispatch_bestofn(True, "feature", 5))


class EmptyClassNonCriticalDisables(unittest.TestCase):
    def test_empty_class_budget_9_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "", 9))


class CaseSensitiveClassDisables(unittest.TestCase):
    def test_uppercase_feature_disables(self):
        self.assertFalse(should_dispatch_bestofn(False, "FEATURE", 5))


if __name__ == "__main__":
    unittest.main()
