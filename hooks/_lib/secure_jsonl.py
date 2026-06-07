"""Shared secure-JSONL appender for sandbox-verify modules.

Single source of truth for the `mkdir(parents=True, exist_ok=True)` +
`os.open(O_WRONLY|O_CREAT|O_APPEND, 0o600)` + `os.write` + `os.close` in
`finally` pattern. Extracted from `sandbox_verify_skip._append_jsonl` and
`sandbox_cost_meter._append_secure_jsonl` (DRY-on-2nd-occurrence).

Two motivations carry forward from the original copies:

1. Mode `0o600` hardens the Story-1 security LOW (was `0o644`).
2. Parent directory created at 0o700 (world-unlistable) so session dirs
   are not enumerable by other local users.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def append_secure_jsonl(path: Path, record: dict) -> None:
    """Append one JSON line to `path` with mode 0o600.

    Creates parent directories at 0o700. The `finally` block guarantees
    the file descriptor closes even if `os.write` raises.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    line = json.dumps(record).encode("utf-8") + b"\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
