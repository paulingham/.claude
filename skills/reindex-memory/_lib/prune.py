"""Delete orphan embedding rows after a drift-triggered schema rebuild."""
import sqlite3

_PRUNE_SQL = ("DELETE FROM embeddings WHERE content_hash NOT IN "
              "(SELECT content_hash FROM observations "
              "UNION SELECT content_hash FROM scratchpad_findings)")


def prune_orphan_embeddings(db_path):
    """Delete embeddings whose content_hash has no matching row."""
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(_PRUNE_SQL)
        con.commit()
    finally:
        con.close()
