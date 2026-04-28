"""Archive past-retention entries from observations.jsonl.

Lines older than ``retention_days`` are appended to gzip files grouped by
the line's calendar month. Lines without a parseable timestamp are KEPT.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from learning_gc_archive_io import (append_gz, atomic_write_lines,
                                    split_lines_by_age)


def _has_content(obs_path: Path) -> bool:
    return obs_path.exists() and obs_path.stat().st_size > 0


def _flush_archives(by_month, archive_dir: Path) -> int:
    for month, lines in by_month.items():
        append_gz(archive_dir / f"observations-{month}.jsonl.gz", lines)
    return sum(len(v) for v in by_month.values())


def _commit_archive(obs_path: Path, keep, by_month, archive_dir: Path) -> int:
    archived = _flush_archives(by_month, archive_dir)
    atomic_write_lines(obs_path, keep)
    return archived


def archive_observations(obs_path, archive_dir, retention_days: int) -> int:
    obs_path = Path(obs_path)
    if not _has_content(obs_path):
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    keep, by_month = split_lines_by_age(obs_path, cutoff)
    if not by_month:
        return 0
    return _commit_archive(obs_path, keep, by_month, Path(archive_dir))
