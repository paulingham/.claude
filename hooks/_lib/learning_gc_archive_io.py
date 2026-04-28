"""IO helpers for learning_gc_archive: parse, gzip-append, atomic-rewrite."""
import gzip
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def _classify(line: str, cutoff: datetime):
    try:
        ts_raw = json.loads(line)["timestamp"]
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except (KeyError, ValueError, json.JSONDecodeError):
        return None, None
    return (ts < cutoff), ts.strftime("%Y-%m")


def _route_line(line: str, cutoff, keep, by_month):
    is_old, month = _classify(line, cutoff)
    if is_old:
        by_month.setdefault(month, []).append(line)
    else:
        keep.append(line)


def split_lines_by_age(obs_path, cutoff: datetime):
    keep, by_month = [], {}
    for raw in Path(obs_path).read_text().splitlines():
        if raw:
            _route_line(raw, cutoff, keep, by_month)
    return keep, by_month


def append_gz(archive_file, lines):
    archive_file = Path(archive_file)
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(archive_file, "at") as fh:
        for line in lines:
            fh.write(line + "\n")


def atomic_write_lines(target_path, lines):
    target_path = Path(target_path)
    body = ("\n".join(lines) + "\n") if lines else ""
    fd, tmp = tempfile.mkstemp(dir=target_path.parent, prefix=".obs.")
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    os.replace(tmp, target_path)
