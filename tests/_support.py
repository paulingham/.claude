"""Shared test helpers for reindex tests. Keeps per-test files small."""
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL_DIR = str(REPO_ROOT / "skills" / "reindex-memory")
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

import reindex  # noqa: E402


def list_tables(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','virtual') OR sql LIKE '%VIRTUAL%'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def fixture_rows():
    return [
        {"session_id": "s1", "timestamp": "2026-04-01T00:00:00Z",
         "tool": "Read", "file": "/a.py", "outcome": "success"},
        {"session_id": "s1", "timestamp": "2026-04-01T00:00:01Z",
         "tool": "Edit", "file": "/a.py", "outcome": "success"},
        {"session_id": "s2", "timestamp": "2026-04-01T00:00:02Z",
         "tool": "Bash", "file": "", "outcome": "success"},
    ]


def count_rows(db, table):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def build_populated_db(tmp):
    db = Path(tmp) / "memory.sqlite"
    learning = Path(tmp) / "learning"
    write_jsonl(learning / "pha" / "observations.jsonl", fixture_rows())
    reindex.run(db_path=db, learning_root=learning)
    return db, learning


def write_malformed_jsonl(tmp, text):
    db = Path(tmp) / "memory.sqlite"
    learning = Path(tmp) / "learning"
    p = learning / "pha" / "observations.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text(text)
    return db, learning


def seed_stale_embeddings(db, surviving_hash):
    """Seed two embeddings (surviving + orphan) and rewind schema_version."""
    con = sqlite3.connect(str(db))
    try:
        _insert_embedding(con, surviving_hash, b"\x00" * 1536)
        _insert_embedding(con, "orphan_hash_xxx", b"\x01" * 1536)
        con.execute("UPDATE schema_version SET version = 0 WHERE version = 1")
        con.commit()
    finally:
        con.close()


def _insert_embedding(con, content_hash, vector):
    con.execute(
        "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
        "VALUES (?, 'bge-small-en-v1.5', 384, ?)",
        (content_hash, vector))


def first_observation_hash(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT content_hash FROM observations LIMIT 1").fetchone()[0]
    finally:
        con.close()


def count_embeddings_for(db, content_hash):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT COUNT(*) FROM embeddings WHERE content_hash=?",
            (content_hash,)).fetchone()[0]
    finally:
        con.close()


def read_schema_version(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT MAX(version) FROM schema_version").fetchone()[0]
    finally:
        con.close()


def restore_current_version(db):
    """Set schema_version back to CURRENT so ensure() will not rebuild."""
    con = sqlite3.connect(str(db))
    try:
        con.execute("UPDATE schema_version SET version = 1")
        con.commit()
    finally:
        con.close()


def count_fts_match(db, term):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT COUNT(*) FROM observations_fts "
            "WHERE observations_fts MATCH ?", (term,)).fetchone()[0]
    finally:
        con.close()


def build_populated_db_with_private_row(tmp):
    """Populate DB via S1 ingest, then raw-insert one is_private=1 row."""
    db, learning = build_populated_db(tmp)
    _insert_private_observation(db)
    return db, learning


def _insert_private_observation(db):
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "INSERT INTO observations "
            "(content_hash, session_id, timestamp, tool, is_private, "
            "searchable_text) VALUES "
            "('privhash', 'sp', '2026-04-01T00:00:10Z', 'Secret', 1, "
            "'Secret private marker')")
        con.commit()
    finally:
        con.close()


def insert_scratchpad_rows(db_path, rows):
    """Direct INSERT into scratchpad_findings; FTS5 triggers auto-populate."""
    con = sqlite3.connect(str(db_path))
    try:
        con.executemany(
            "INSERT INTO scratchpad_findings "
            "(content_hash, task_id, category, agent_role, phase, "
            "timestamp, body, is_private) VALUES "
            "(:hash, :task, :cat, :role, :phase, :ts, :body, :priv)", rows)
        con.commit()
    finally:
        con.close()
