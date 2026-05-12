"""AC3: emit SANDBOX_SKIPPED when E2B_API_KEY is missing.

`emit_skip_if_no_token(session_id, metrics_dir) -> dict`:

- Returns `{"verdict": "SANDBOX_SKIPPED", "reason": "no-e2b-token",
            "timestamp": <ISO-8601>}` when `E2B_API_KEY` is unset/empty.
- Appends exactly one JSON line to
  `{metrics_dir}/{session_id}/sandbox-verify-skips.jsonl` using
  `os.open(O_WRONLY|O_CREAT|O_APPEND)` + `os.write` — the bash-write-guard
  hook blocks `>>` to `.jsonl` files, so the Python file-descriptor path
  is the canonical append shape (mirrors `hooks/_lib/log-injection.sh`).
- Returns `{"verdict": "SANDBOX_VERIFIED_TBD"}` when the token IS set —
  Story 3 will replace this branch with actual provisioning. Story-1
  scope is the no-token branch only; the token-present branch is a
  placeholder so callers can detect that provisioning has not yet
  shipped.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path


def _utc_now_iso8601():
    """ISO-8601 timestamp in UTC, e.g. `2026-05-12T13:45:09Z`."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(path, record):
    """Append one JSON line to `path`, creating parents as needed.

    Uses `os.open` + `os.write` to bypass the bash-write-guard hook
    that blocks shell `>>` to `.jsonl`. Mirrors the canonical pattern
    documented in `session-memory/.../fragility.md` § bash-write-guard.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record).encode("utf-8") + b"\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def emit_skip_if_no_token(session_id, metrics_dir):
    """Story-1 contract: emit SANDBOX_SKIPPED when E2B_API_KEY is missing.

    Args:
      session_id: identifier for the skip-log subdirectory.
      metrics_dir: parent directory under which `<session_id>/...jsonl`
        lives. Created if absent.

    Returns:
      Dict with `verdict`, `reason`, `timestamp` keys when the token is
      missing. Story 3 will replace the token-present branch with real
      provisioning; Story-1 marks it `SANDBOX_VERIFIED_TBD` so callers
      can detect the un-shipped path.
    """
    token = os.environ.get("E2B_API_KEY", "")
    if token:
        return {"verdict": "SANDBOX_VERIFIED_TBD",
                "reason": "story-3-not-shipped",
                "timestamp": _utc_now_iso8601()}

    timestamp = _utc_now_iso8601()
    record = {"reason": "no-e2b-token", "timestamp": timestamp,
              "session_id": session_id}
    jsonl_path = Path(metrics_dir) / session_id / "sandbox-verify-skips.jsonl"
    _append_jsonl(jsonl_path, record)
    return {"verdict": "SANDBOX_SKIPPED", "reason": "no-e2b-token",
            "timestamp": timestamp}
