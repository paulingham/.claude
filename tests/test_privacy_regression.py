"""AC8 regression guard: all 6 recall privacy surfaces filter is_private=0."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from _support import count_rows  # noqa: F401 — puts _lib on sys.path
from _lib import schema  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import timeline_tier, search_tier, hydrate_tier  # noqa: E402


def _seed(db):
    """Insert 1 public + 1 private observation, 1 public + 1 private finding."""
    con = sqlite3.connect(str(db))
    try:
        con.executescript("""
INSERT INTO observations (content_hash, session_id, timestamp, tool, file,
  outcome, is_private, searchable_text)
VALUES ('h_pub', 's', '2026-04-01T00:00:00Z', 'Read', '/a.py', 'ok', 0, 'Read /a.py ok'),
       ('h_priv', 's', '2026-04-01T00:00:01Z', 'Read', '/s.env', 'secret', 1, 'Read /s.env secret');
INSERT INTO scratchpad_findings (content_hash, task_id, category, agent_role,
  phase, timestamp, body, is_private)
VALUES ('f_pub', 't', 'discovery', 'eng', 'build',
        '2026-04-01T00:00:00Z', 'public body', 0),
       ('f_priv', 't', 'warning', 'eng', 'build',
        '2026-04-01T00:00:01Z', 'private body', 1);
""")
        con.commit()
    finally:
        con.close()


def _db():
    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "m.sqlite"
    schema.ensure(db)
    _seed(db)
    return db


class TimelineObservationsHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_row(self):
        rows = timeline_tier.fetch_observations(_db())
        self.assertEqual([r["outcome"] for r in rows], ["ok"])


class TimelineScratchpadHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_finding(self):
        rows = timeline_tier.fetch_scratchpad(_db())
        self.assertEqual([r["category"] for r in rows], ["discovery"])


class SearchObservationsHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_hit(self):
        hits = search_tier.search_observations(_db(), "secret")
        self.assertEqual(hits, [])


class SearchScratchpadHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_hit(self):
        hits = search_tier.search_scratchpad(_db(), "private")
        self.assertEqual(hits, [])


class HydrateObservationsByHashHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_hash(self):
        rows = hydrate_tier.fetch_by_hashes(_db(), ["h_pub", "h_priv"])
        self.assertEqual([r["content_hash"] for r in rows], ["h_pub"])


class HydrateScratchpadByHashHidesPrivate(unittest.TestCase):
    def test_default_excludes_private_hash(self):
        rows = hydrate_tier.fetch_findings_by_hashes(
            _db(), ["f_pub", "f_priv"])
        self.assertEqual([r["content_hash"] for r in rows], ["f_pub"])


if __name__ == "__main__":
    unittest.main()
