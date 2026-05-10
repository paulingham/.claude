"""Cache-aware bulk extractor — read-through SQLite cache keyed on (file, mtime).

For each requested file:
- if cached rows exist with a matching mtime, return them verbatim
  (zero parser invocations on the hot path)
- otherwise, re-extract via `extract_tags()` and replace any prior
  rows for the file in a single transaction (atomic invalidation,
  AC5).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from codebase_map.tags_types import Tag


def cached_tags(
    db_path: Path,
    files: Iterable[Path | str],
    extractor,
) -> list[Tag]:
    paths = [Path(f) for f in files]
    con = sqlite3.connect(str(db_path))
    try:
        return _bulk(con, paths, extractor)
    finally:
        con.close()


def _bulk(con: sqlite3.Connection, files: list[Path], extractor
          ) -> list[Tag]:
    out: list[Tag] = []
    for f in files:
        out.extend(_one(con, f, extractor))
    return out


def _one(con: sqlite3.Connection, file: Path, extractor) -> list[Tag]:
    mtime = file.stat().st_mtime
    cached = _read(con, file, mtime)
    if cached:
        return cached
    return _refresh(con, file, mtime, extractor)


def _read(con: sqlite3.Connection, file: Path, mtime: float) -> list[Tag]:
    rows = con.execute(
        "SELECT file, mtime, kind, name, line, col, lang "
        "FROM tags WHERE file=? AND mtime=?",
        (str(file), mtime),
    ).fetchall()
    return [Tag(*row) for row in rows]


def _refresh(con: sqlite3.Connection, file: Path, mtime: float,
             extractor) -> list[Tag]:
    fresh = extractor(file)
    with con:  # implicit atomic transaction
        con.execute("DELETE FROM tags WHERE file=?", (str(file),))
        if fresh:
            con.executemany(
                "INSERT INTO tags "
                "(file, mtime, kind, name, line, col, lang) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [tuple(t) for t in fresh],
            )
    return fresh
