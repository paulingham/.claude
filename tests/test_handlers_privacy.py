"""Privacy gate + per-tool arg whitelist enforcement (AC9)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from _support import build_populated_db_with_private_row  # noqa: E402
from mcp_memory._lib import handlers  # noqa: E402
from recall import recall  # noqa: E402


class TestPrivacyRowHidden(unittest.TestCase):
    def test_private_row_excluded_from_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db_with_private_row(tmp)
            env = handlers.search_memory(
                {"query": "Secret", "db_path": str(db),
                 "source": "observations"})
            self.assertEqual(env["hits"], [])


class TestIncludePrivateArgDropped(unittest.TestCase):
    def test_include_private_not_forwarded_to_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db_with_private_row(tmp)
            seen_kwargs = {}
            original = recall.search

            def spy(*args, **kw):
                seen_kwargs.update(kw)
                return original(*args, **kw)

            recall.search = spy
            try:
                env = handlers.search_memory({
                    "query": "Secret", "db_path": str(db),
                    "source": "observations",
                    "include_private": True})
            finally:
                recall.search = original
            self.assertNotIn("include_private", seen_kwargs)
            self.assertEqual(env["hits"], [])


class TestUnknownArgIgnored(unittest.TestCase):
    def test_unknown_argument_is_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db_with_private_row(tmp)
            seen_kwargs = {}
            original = recall.timeline

            def spy(*args, **kw):
                seen_kwargs.update(kw)
                return original(*args, **kw)

            recall.timeline = spy
            try:
                handlers.get_timeline({
                    "source": "observations", "db_path": str(db),
                    "random_key": "ignore_me"})
            finally:
                recall.timeline = original
            self.assertNotIn("random_key", seen_kwargs)


if __name__ == "__main__":
    unittest.main()
