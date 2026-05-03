"""Best-of-N gate predicate tests (incremental TDD)."""
import unittest

from bestofn_gate import should_dispatch_bestofn


class CriticalEnables(unittest.TestCase):
    def test_critical_bug_low_budget_enables(self):
        self.assertTrue(should_dispatch_bestofn(True, "bug", 2))

    def test_critical_feature_enables(self):
        self.assertTrue(should_dispatch_bestofn(True, "feature", 5))


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


if __name__ == "__main__":
    unittest.main()
