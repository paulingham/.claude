"""Source-dispatch helpers shared by recall public API."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import dispatch  # noqa: E402


class GuardedDecorator(unittest.TestCase):
    def test_returns_empty_when_db_missing(self):
        wrapped = dispatch.guarded(lambda *, db_path: [1, 2, 3])
        self.assertEqual(wrapped(db_path=Path("/no/such.sqlite")), [])

    def test_forwards_when_db_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            wrapped = dispatch.guarded(lambda *, db_path: "ok")
            self.assertEqual(wrapped(db_path=db), "ok")


class SearchDispatch(unittest.TestCase):
    def test_observations_source_picks_obs_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            out = dispatch.search("Read", 5, "observations", db, False)
            self.assertTrue(all("source" not in h for h in out))


if __name__ == "__main__":
    unittest.main()
