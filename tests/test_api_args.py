"""Shared arg normalisation: db default, limit clamp, id cap, source check."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"
                       / "reindex-memory"))
from recall._lib import api_args  # noqa: E402


class ResolveDb(unittest.TestCase):
    def test_none_resolves_to_default_db(self):
        resolved = api_args.resolve_db(None)
        self.assertTrue(str(resolved).endswith("memory.sqlite"))

    def test_explicit_path_passthrough(self):
        self.assertEqual(api_args.resolve_db("/tmp/x"), "/tmp/x")


class ClampLimit(unittest.TestCase):
    def test_clamps_to_max(self):
        self.assertEqual(api_args.clamp_limit(10_000), api_args.MAX_LIMIT)

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            api_args.clamp_limit(0)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            api_args.clamp_limit(-1)


class CapIds(unittest.TestCase):
    def test_over_cap_rejected(self):
        with self.assertRaises(ValueError):
            api_args.cap_ids(list(range(api_args.MAX_IDS + 1)))

    def test_at_cap_allowed(self):
        v = list(range(api_args.MAX_IDS))
        self.assertEqual(len(api_args.cap_ids(v)), api_args.MAX_IDS)


class CheckSource(unittest.TestCase):
    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            api_args.check_source("nonsense")

    def test_known_sources_allowed(self):
        for src in ("both", "observations", "scratchpad"):
            api_args.check_source(src)  # does not raise


if __name__ == "__main__":
    unittest.main()
