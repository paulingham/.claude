"""state.json read/write helpers for the codebase-map hooks.

Mirrors `hooks/_lib/learning_gc_state.py` — atomic write via tempfile +
os.replace; tolerant read returns None on any decode error.

State file layout:
    ~/.claude/db/codebase-map/{project-hash}/state.json
        {
            "last_built_sha": "<git rev-parse main>",
            "last_built_at":  "<ISO 8601 UTC>"
        }

The hook contract requires the new SHA to be persisted BEFORE the
expensive rebuild subprocess runs. That ordering means a 10s
SessionStart timeout (or SIGSEGV in tree-sitter) does NOT loop the
user through retries — the next session-start sees the SHA already
advanced and runs the rebuild as a normal hit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_HASH_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")


def read_state(state_path) -> dict | None:
    """Return the parsed state dict, or None if missing/malformed."""
    try:
        return json.loads(Path(state_path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def last_built_sha(state_path) -> str | None:
    """Return the cached `last_built_sha` field, or None."""
    state = read_state(state_path)
    if state is None:
        return None
    sha = state.get("last_built_sha")
    if not isinstance(sha, str) or not sha:
        return None
    return sha


def write_state(state_path, last_built_sha: str) -> None:
    """Atomic write of the state.json file."""
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "last_built_sha": last_built_sha,
            "last_built_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    fd, tmp = tempfile.mkstemp(dir=state_path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp, state_path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def validate_project_hash(raw: str | None, fallback: str = "local") -> str:
    """AC20: regex-validate the env value; fall back on rejection."""
    if not raw:
        return fallback
    return raw if PROJECT_HASH_REGEX.match(raw) else fallback


def _cli_main(argv) -> int:
    parser = argparse.ArgumentParser(prog="codebase-map-state.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub_read = sub.add_parser("read")
    sub_read.add_argument("path")
    sub_read.add_argument("--field", default=None)
    sub_write = sub.add_parser("write")
    sub_write.add_argument("path")
    sub_write.add_argument("sha")
    sub_validate = sub.add_parser("validate-hash")
    sub_validate.add_argument("raw", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.cmd == "read":
        return _read_cli(args)
    if args.cmd == "write":
        write_state(args.path, args.sha)
        return 0
    if args.cmd == "validate-hash":
        print(validate_project_hash(args.raw))
        return 0
    return 2


def _read_cli(args) -> int:
    state = read_state(args.path)
    if state is None:
        return 1
    if args.field:
        value = state.get(args.field)
        if value is None:
            return 1
        print(value)
        return 0
    print(json.dumps(state))
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main(sys.argv[1:]))
