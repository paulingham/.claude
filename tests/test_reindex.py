"""Acceptance-criterion tests for reindex.py."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from _support import (build_populated_db, count_embeddings_for, count_fts_match,
                      count_rows, first_observation_hash, list_tables,
                      read_schema_version, reindex, seed_stale_embeddings,
                      write_malformed_jsonl)


class AC1SchemaCreated(unittest.TestCase):
    def test_creates_db_with_all_tables_and_version_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            learning = Path(tmp) / "learning"
            learning.mkdir()
            reindex.run(db_path=db, learning_root=learning)
            expected = {"observations", "observations_fts",
                        "scratchpad_findings", "scratchpad_fts",
                        "embeddings", "privacy_allowlist", "schema_version"}
            self.assertTrue(expected.issubset(list_tables(db)))
            self.assertEqual(read_schema_version(db), 1)


class AC2NRowsInserted(unittest.TestCase):
    def test_jsonl_rows_populate_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            self.assertEqual(count_rows(db, "observations"), 3)


class AC3IdempotentDedup(unittest.TestCase):
    def test_second_run_inserts_zero_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = build_populated_db(tmp)
            before = count_rows(db, "observations")
            summary = reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(count_rows(db, "observations"), before)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(summary.skipped, 3)


class AC4MalformedRowsSkipped(unittest.TestCase):
    def test_bad_rows_logged_good_rows_inserted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = write_malformed_jsonl(
                tmp,
                '{"session_id":"s1","timestamp":"t1","tool":"Read"}\n'
                'not json at all\n'
                '{"session_id":"s2","timestamp":"t2","tool":"Edit"}\n')
            err = io.StringIO()
            with redirect_stderr(err):
                summary = reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(count_rows(db, "observations"), 2)
            self.assertGreaterEqual(summary.bad, 1)
            self.assertIn("skip", err.getvalue())


class AC4ExitCodeZero(unittest.TestCase):
    def test_main_returns_zero_when_bad_rows_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = write_malformed_jsonl(
                tmp, 'not json\n{"tool":"X","timestamp":"t","session_id":"s"}\n')
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                rc = reindex.main(
                    ["--db", str(db), "--learning", str(learning)])
            self.assertEqual(rc, 0)


class AC5SchemaDriftRebuild(unittest.TestCase):
    def test_drift_drops_observations_preserves_mapped_embeddings(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = build_populated_db(tmp)
            surviving = first_observation_hash(db)
            seed_stale_embeddings(db, surviving)
            reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(count_rows(db, "observations"), 3)
            self.assertEqual(count_embeddings_for(db, surviving), 1)
            self.assertEqual(count_embeddings_for(db, "orphan_hash_xxx"), 0)
            self.assertEqual(read_schema_version(db), 1)


class AC6FTSPlausible(unittest.TestCase):
    def test_fts_query_returns_nonneg_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            n = count_fts_match(db, "Read")
            self.assertIsInstance(n, int)
            self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
