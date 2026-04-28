"""GC state management for the learning DB hygiene hook.

State is stored at ``learning/{project-hash}/.gc-state.json`` as
``{"last_run": "<ISO 8601 UTC>"}``. The file is missing on first run.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def _read_last_run(state_path) -> Optional[datetime]:
    try:
        raw = Path(state_path).read_text()
        ts = json.loads(raw).get("last_run")
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (OSError, ValueError, AttributeError, json.JSONDecodeError):
        return None


def is_gc_due(state_path, interval_days: int = 30) -> bool:
    last = _read_last_run(state_path)
    if last is None:
        return True
    return datetime.now(timezone.utc) - last >= timedelta(days=interval_days)


def update_state(state_path) -> None:
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"last_run": datetime.now(timezone.utc).isoformat()})
    fd, tmp = tempfile.mkstemp(dir=state_path.parent, prefix=".gc-state.")
    with os.fdopen(fd, "w") as fh:
        fh.write(payload)
    os.replace(tmp, state_path)
