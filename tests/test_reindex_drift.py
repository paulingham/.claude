"""AC5 drift-related acceptance tests."""
import tempfile
import unittest

from _support import (build_populated_db, count_embeddings_for, count_rows,
                      first_observation_hash, read_schema_version, reindex,
                      restore_current_version, seed_stale_embeddings)


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


class AC5NoDriftSkipsPrune(unittest.TestCase):
    def test_orphan_embedding_retained_without_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = build_populated_db(tmp)
            surviving = first_observation_hash(db)
            seed_stale_embeddings(db, surviving)
            restore_current_version(db)
            reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(count_embeddings_for(db, "orphan_hash_xxx"), 1)


if __name__ == "__main__":
    unittest.main()
