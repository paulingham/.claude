"""Shared arg normalisation: db_path default, limit clamp, id cap."""
import sys
from pathlib import Path

_REINDEX = str(Path(__file__).resolve().parents[3]
               / "skills" / "reindex-memory")
if _REINDEX not in sys.path:
    sys.path.insert(0, _REINDEX)
from _lib import paths  # noqa: E402

MAX_LIMIT = 500
MAX_IDS = 100
_SOURCES = ("both", "observations", "scratchpad")


def check_source(source):
    if source not in _SOURCES:
        raise ValueError(f"unknown source: {source}")


def resolve_db(db_path):
    return db_path if db_path is not None else paths.default_db()


def clamp_limit(limit):
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive int")
    return min(limit, MAX_LIMIT)


def cap_ids(values):
    if len(values) > MAX_IDS:
        raise ValueError(f"too many ids (max {MAX_IDS})")
    return values


def swallow_filter_error(exc):
    sys.stderr.write(f"recall: {exc}\n")
    return []


def guarded_call(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ValueError as exc:
        return swallow_filter_error(exc)
