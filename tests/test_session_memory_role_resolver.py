"""AC15 — Role-mapping resolver matches the documented § 4.2 table.

The Python resolver module's role → sub-file mapping is the SOURCE OF
TRUTH for orchestrator routing. This snapshot test pins both directions:
- Every entry in the documented table maps to the same list in the resolver.
- The resolver exposes a CANONICAL_SUBFILES tuple matching the 5 sub-file
  basenames.
"""
import unittest

from session_memory_role_resolver import (
    CANONICAL_SUBFILES,
    is_generated_subfile,
    resolve_subfiles_for_role,
)

EXPECTED_TABLE = {
    "architect":               ["codebase-map", "patterns", "fragility"],
    "software-engineer":       ["build-test", "patterns", "fragility"],
    "frontend-engineer":       ["build-test", "patterns", "fragility"],
    "database-engineer":       ["build-test", "patterns", "fragility"],
    "infrastructure-engineer": ["build-test", "fragility"],
    "qa-engineer":             ["build-test", "fragility"],
    "code-reviewer":           ["patterns", "fragility"],
    "security-engineer":       ["patterns", "fragility"],
    "product-reviewer":        [],
    "patch-critic":            ["fragility"],
    "session-memory-updater":  [],
}


class CanonicalSubfilesMatchesPlan(unittest.TestCase):
    def test_canonical_subfiles_is_tuple(self):
        self.assertIsInstance(CANONICAL_SUBFILES, tuple)

    def test_canonical_subfiles_has_five_entries(self):
        self.assertEqual(len(CANONICAL_SUBFILES), 5)

    def test_canonical_subfiles_set(self):
        self.assertEqual(
            set(CANONICAL_SUBFILES),
            {"codebase-map", "build-test", "patterns", "fragility", "active-work"},
        )


class ResolverMatchesDocumentedTableForAllCanonicalRoles(unittest.TestCase):
    def test_resolver_matches_documented_table_for_all_canonical_roles(self):
        for role, expected in EXPECTED_TABLE.items():
            actual = resolve_subfiles_for_role(role)
            self.assertEqual(
                actual, expected,
                f"role={role}: expected {expected}, got {actual}",
            )

    def test_resolver_returns_empty_for_unknown_role(self):
        self.assertEqual(resolve_subfiles_for_role("totally-made-up"), [])


class IsGeneratedSubfilePredicateMatchesPlanSliceD(unittest.TestCase):
    """AC22 — `is_generated_subfile` flags codebase-map only.

    Generator-owned (codebase-map.md is rebuilt on every SessionStart) is
    orthogonal to the canonical sub-file list — the resolver still must
    enumerate codebase-map for the architect's injection list, but the
    updater-dispatch hook must permanently refuse to spawn an updater
    for it.
    """

    def test_ac22_is_generated_subfile_predicate(self):
        # Three assertions per plan §3 Slice D AC22.
        self.assertTrue(is_generated_subfile("codebase-map"))
        self.assertFalse(is_generated_subfile("patterns"))
        self.assertFalse(is_generated_subfile("totally-unknown"))


if __name__ == "__main__":
    unittest.main()
