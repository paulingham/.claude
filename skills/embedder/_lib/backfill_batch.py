"""Per-batch embed write for backfill CLI. BEGIN IMMEDIATE per batch."""
from embedder.embedder import get_embedder

BATCH = 100


def process(con, stats):
    rows = _missing(con)
    if not rows:
        return False
    _write(con, rows, stats)
    return True


def _missing(con):
    return con.execute(
        "SELECT o.content_hash, o.searchable_text FROM observations o "
        "LEFT JOIN embeddings e ON e.content_hash = o.content_hash "
        "WHERE e.content_hash IS NULL LIMIT ?", (BATCH,)).fetchall()


def _write(con, rows, stats):
    con.execute("BEGIN IMMEDIATE")
    for content_hash, text in rows:
        _embed_one(con, content_hash, text or "", stats)
    con.commit()


def _embed_one(con, content_hash, text, stats):
    stats["processed"] += 1
    try:
        _insert(con, content_hash, get_embedder().encode(text))
        stats["inserted"] += 1
    except Exception:
        stats["errors"] += 1


def _insert(con, content_hash, vec):
    con.execute(
        "INSERT OR REPLACE INTO embeddings "
        "(content_hash, model_id, dim, vector) VALUES (?, ?, ?, ?)",
        (content_hash, "bge-small-en-v1.5", 384, vec))
