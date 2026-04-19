"""Backfill CLI — embed observations missing from embeddings table.

Privacy note: privacy is enforced at recall query time (is_private filter),
not at backfill time. Backfill embeds every observation row, including
is_private=1, so that future privacy-mode toggles do not require a rebuild.
Rows are keyed by content_hash and INSERT OR REPLACE'd so repeat runs are
idempotent.
"""
import sqlite3
import sys
import time

from embedder._lib import backfill_batch

SLEEP = 0.05


def run(db_path):
    con = sqlite3.connect(str(db_path), timeout=5.0)
    try:
        return _loop(con)
    finally:
        con.close()


def _loop(con):
    stats = {"processed": 0, "inserted": 0, "skipped": 0, "errors": 0}
    while backfill_batch.process(con, stats):
        time.sleep(SLEEP)
    return stats


def main(argv=None):
    from embedder._lib import backfill_cli
    args = backfill_cli.parse(argv)
    stats = run(args.db)
    sys.stdout.write(backfill_cli.format_summary(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
