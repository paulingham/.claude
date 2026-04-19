"""CLI envelope + missing-DB guard shared across tiers."""
import sys
from pathlib import Path


def db_missing(db_path):
    """Stderr warning + return True when db_path does not exist."""
    if db_path and Path(db_path).exists():
        return False
    sys.stderr.write(f"recall: db missing at {db_path} — run reindex-memory\n")
    return True


def envelope(tier, hits, limit):
    truncated = len(hits) >= limit
    return {"tier": tier, "hits": hits, "total": len(hits),
            "truncated": truncated}
