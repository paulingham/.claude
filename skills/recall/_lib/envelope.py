"""CLI envelope + missing-DB guard shared across tiers."""
import sys
from pathlib import Path


def db_missing(db_path):
    """Stderr warning + return True when db_path does not exist."""
    if db_path and Path(db_path).exists():
        return False
    safe = repr(str(db_path))
    sys.stderr.write(f"recall: db missing at {safe} — run reindex-memory\n")
    return True


def envelope(tier, hits, limit, fetched=None):
    raw = fetched if fetched is not None else len(hits)
    return {"tier": tier, "hits": hits, "total": len(hits),
            "truncated": raw > limit}
