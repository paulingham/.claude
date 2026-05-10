"""Tier 0 contract — `is_generated_subfile` signature + CANONICAL_SUBFILES invariant (Slice D).

Pins the public surface introduced for codebase-map's permanent generator-owned
artifact status. Two invariants:

1. `is_generated_subfile(sub: str) -> bool` exists and accepts a string,
   returns a bool. The predicate is the gate the role-resolver layer + the
   updater-dispatch hook consult to decide whether a sub-file is generator-owned.
2. `CANONICAL_SUBFILES` is unchanged (still 5 entries). Generated-vs-writable is
   orthogonal to canonical list — the resolver still must enumerate
   codebase-map for the architect's injection list.
"""
import inspect
import unittest

from session_memory_role_resolver import CANONICAL_SUBFILES, is_generated_subfile


class IsGeneratedSubfileSignaturePinned(unittest.TestCase):
    def test_predicate_is_callable(self):
        self.assertTrue(callable(is_generated_subfile))

    def test_predicate_returns_bool(self):
        # Bool by signature, not just truthy-falsy.
        result = is_generated_subfile("codebase-map")
        self.assertIsInstance(result, bool)

    def test_predicate_accepts_one_string_argument(self):
        sig = inspect.signature(is_generated_subfile)
        params = list(sig.parameters.values())
        self.assertEqual(len(params), 1, f"expected 1 arg, got {len(params)}")
        self.assertEqual(params[0].annotation, str)
        self.assertEqual(sig.return_annotation, bool)


class CanonicalSubfilesUnchangedByGeneratedPredicate(unittest.TestCase):
    """Generated-vs-writable is orthogonal to canonical list."""

    def test_canonical_subfiles_still_five_entries(self):
        self.assertEqual(len(CANONICAL_SUBFILES), 5)

    def test_canonical_subfiles_set_unchanged(self):
        self.assertEqual(
            set(CANONICAL_SUBFILES),
            {"codebase-map", "build-test", "patterns", "fragility", "active-work"},
        )


if __name__ == "__main__":
    unittest.main()
