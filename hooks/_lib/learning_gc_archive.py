"""Archive past-retention entries from observations.jsonl.

Lines older than ``retention_days`` are appended to gzip files grouped by
the line's calendar month. Lines without a parseable timestamp are KEPT.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from learning_gc_archive_io import (append_gz, atomic_write_lines,
                                    split_lines_by_age)


def archive_observations(obs_path, archive_dir, retention_days: int) -> int:
    obs_path = Path(obs_path)
    if not obs_path.exists() or obs_path.stat().st_size == 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    keep, by_month = split_lines_by_age(obs_path, cutoff)
    archived = sum(len(v) for v in by_month.values())
    if archived == 0:
        return 0
    for month, lines in by_month.items():
        append_gz(Path(archive_dir) /
                  f"observations-{month}.jsonl.gz", lines)
    atomic_write_lines(obs_path, keep)
    return archived
