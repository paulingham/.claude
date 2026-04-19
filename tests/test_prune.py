"""Unit tests for _lib.prune.prune_orphan_embeddings."""
import sqlite3
import tempfile
import unittest

from _support import (build_populated_db, count_embeddings_for,
                      first_observation_hash)  # adds skills/reindex-memory to sys.path
from _lib import prune  # noqa: E402


def _insert_embedding(db, content_hash):
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
        "VALUES (?, 'bge-small-en-v1.5', 384, ?)",
        (content_hash, b"\x00" * 1536))
    con.commit()
    con.close()


class PruneRemovesOnlyOrphans(unittest.TestCase):
    def test_keeps_matched_drops_unmatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            matched = first_observation_hash(db)
            _insert_embedding(db, matched)
            _insert_embedding(db, "zzz_orphan")
            prune.prune_orphan_embeddings(db)
            self.assertEqual(count_embeddings_for(db, matched), 1)
            self.assertEqual(count_embeddings_for(db, "zzz_orphan"), 0)


if __name__ == "__main__":
    unittest.main()
