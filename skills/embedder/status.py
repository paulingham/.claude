"""Atomic JSON status writer for embedder readiness.

Path: $CLAUDE_EMBEDDER_STATUS or ~/.claude/state/embedder-status.json.
Write is atomic (tempfile + rename) so concurrent readers never see a
partial JSON document.
"""
import json
import os
import tempfile
from pathlib import Path

DEFAULT = Path.home() / ".claude" / "state" / "embedder-status.json"


def path():
    return Path(os.environ.get("CLAUDE_EMBEDDER_STATUS") or DEFAULT)


def write(payload):
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, json.dumps(payload, sort_keys=True))


def _atomic_write(target, body):
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".json")
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    os.replace(tmp, target)
