#!/usr/bin/env python3
"""Rebuild ~/.claude/db/memory.sqlite from learning/*/observations.jsonl.

Python stdlib only. Idempotent via UNIQUE content_hash. See SKILL.md.
"""
import argparse
import sys
from pathlib import Path

from _lib import schema, ingest, paths


def run(db_path, learning_root, verbose=False):
    """Apply schema then ingest all JSONL files under learning_root."""
    schema.ensure(db_path)
    return ingest.ingest_all(db_path, learning_root, verbose=verbose)


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Rebuild memory.sqlite from JSONL.")
    p.add_argument("--db", type=Path, default=paths.default_db())
    p.add_argument("--learning", type=Path, default=paths.default_learning())
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    summary = run(args.db, args.learning, verbose=args.verbose)
    print(f"REINDEXED db={args.db} inserted={summary.inserted} "
          f"skipped={summary.skipped} bad={summary.bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
