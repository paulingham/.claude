"""AC4 — Pure-function diff algorithm for sandbox vs worktree pass sets.

Tests `hooks/_lib/sandbox_verify_diff.py:compare_pass_sets()`:

- Equal pass sets → `{"verdict": "SANDBOX_VERIFIED", "diverging_tests": []}`
- Divergent pass sets → `{"verdict": "SANDBOX_FAILED",
                          "diverging_tests": [<names>]}`

Also exercises `parse_test_outcomes(output, runner="pytest")` for the
Story-1 stub parser shape (Story 2 will extend with full pytest output
parsing — Story 1 ships the contract only).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    """Import the module under test lazily so a missing module fails
    inside a test (RED) rather than at collection time."""
    from sandbox_verify_diff import compare_pass_sets, parse_test_outcomes
    return compare_pass_sets, parse_test_outcomes


class CompareEqualPassSetsReturnsVerified(unittest.TestCase):
    def test_compare_pass_sets_equal_returns_verified(self):
        compare_pass_sets, _ = _load()
        worktree = {"t1": "pass", "t2": "fail"}
        sandbox = {"t1": "pass", "t2": "fail"}
        result = compare_pass_sets(worktree, sandbox)
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED")
        self.assertEqual(result["diverging_tests"], [])

    def test_compare_pass_sets_both_empty_returns_verified(self):
        compare_pass_sets, _ = _load()
        result = compare_pass_sets({}, {})
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED")
        self.assertEqual(result["diverging_tests"], [])


class CompareDivergentPassSetsReturnsFailedWithNames(unittest.TestCase):
    def test_compare_pass_sets_divergent_returns_failed_with_names(self):
        compare_pass_sets, _ = _load()
        worktree = {"t1": "pass", "t2": "pass"}
        sandbox = {"t1": "pass", "t2": "fail"}
        result = compare_pass_sets(worktree, sandbox)
        self.assertEqual(result["verdict"], "SANDBOX_FAILED")
        self.assertEqual(result["diverging_tests"], ["t2"])

    def test_compare_pass_sets_only_in_worktree_returns_failed(self):
        compare_pass_sets, _ = _load()
        worktree = {"t1": "pass", "extra": "pass"}
        sandbox = {"t1": "pass"}
        result = compare_pass_sets(worktree, sandbox)
        self.assertEqual(result["verdict"], "SANDBOX_FAILED")
        self.assertEqual(result["diverging_tests"], ["extra"])

    def test_compare_pass_sets_diverging_names_sorted(self):
        compare_pass_sets, _ = _load()
        worktree = {"b": "pass", "a": "pass", "c": "fail"}
        sandbox = {"a": "fail", "b": "fail", "c": "pass"}
        result = compare_pass_sets(worktree, sandbox)
        self.assertEqual(result["verdict"], "SANDBOX_FAILED")
        # Sorted for determinism: 'a', 'b', 'c' all diverge.
        self.assertEqual(result["diverging_tests"], ["a", "b", "c"])


class ParseTestOutcomesStubReturnsEmptyDict(unittest.TestCase):
    """Story-1 stub: parser returns empty dict; Story 2 will fill in
    per-language pytest/jest/rspec parsers. The contract is
    `dict[str, "pass"|"fail"]`; an empty parser is a valid implementation
    that the diff algorithm consumes correctly (both empty → VERIFIED)."""

    def test_parse_test_outcomes_returns_dict(self):
        _, parse_test_outcomes = _load()
        result = parse_test_outcomes("", runner="pytest")
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
