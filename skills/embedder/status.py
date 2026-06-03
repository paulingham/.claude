"""Atomic JSON status writer for embedder readiness.

Path: $CLAUDE_EMBEDDER_STATUS or ~/.claude/state/embedder-status.json.
Write is atomic (tempfile + rename) so concurrent readers never see a
partial JSON document.
"""
import json
import os
import tempfile
from pathlib import Path

from embedder._lib.harness_paths import harness_data

DEFAULT = harness_data() / "state" / "embedder-status.json"


def path():
    return Path(os.environ.get("CLAUDE_EMBEDDER_STATUS") or DEFAULT)


def write(payload):
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, json.dumps(payload, sort_keys=True))


def read():
    target = path()
    if not target.exists():
        return {}
    return json.loads(target.read_text())


def record_success(timestamp):
    _merge({"last_success_at": timestamp})


def record_failure(reason, timestamp):
    _merge({"last_error": reason, "last_error_at": timestamp})


def _merge(fields):
    payload = read()
    payload.update(fields)
    write(payload)


def _atomic_write(target, body):
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".json")
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    os.replace(tmp, target)
