"""Learn-status sentinel for the pre-flight queue mechanism (B8.1).

Schema: ``learning/{project-hash}/.learn-state.json`` gains
``last_learn_started`` (ISO 8601 UTC string) as a companion to the
existing ``last_learn_run``. The pre-flight check defers a pipeline's
Reflect § 6b ``/learn`` invocation when an in-flight run is detected.

Predicate: in-flight ⇔ ``last_learn_started > last_learn_run`` OR
``last_learn_run is None``. Idle otherwise. Symmetric writes are kept
small so concurrent ``/learn`` invocations cannot corrupt the file —
each writer reads-merges-writes the whole document atomically.

JSONL emission MUST use ``json.dumps`` (load-bearing instinct,
confidence 0.6) — never bash ``printf`` for dynamic values.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping, Optional


# Field names — single source of truth.
STARTED = "last_learn_started"
COMPLETED = "last_learn_run"


def mark_started(state_path: str | Path, timestamp: str) -> None:
    """Write the in-progress sentinel before any expensive ``/learn`` work."""
    _merge_write(state_path, {STARTED: timestamp})


def mark_completed(state_path: str | Path, timestamp: str) -> None:
    """Stamp completion. ``last_learn_started`` is preserved for forensics."""
    _merge_write(state_path, {COMPLETED: timestamp})


def is_in_flight(state: Mapping[str, Optional[str]]) -> bool:
    """Predicate: a ``/learn`` run is in flight ⇔ started > completed."""
    started = state.get(STARTED)
    completed = state.get(COMPLETED)
    if started is None:
        return False
    if completed is None:
        return True
    return started > completed


def status_for(state: Mapping[str, Optional[str]]) -> str:
    """``"in-flight"`` when started>completed, else ``"idle"``."""
    return "in-flight" if is_in_flight(state) else "idle"


def status_for_path(state_path: str | Path) -> str:
    """Read state from disk and return status. Missing file → ``"idle"``."""
    state = _read(state_path)
    return status_for(state)


# --- internals -------------------------------------------------------------

_DEFAULT = {
    COMPLETED: None,
    STARTED: None,
    "pipelines_since_learn": 0,
    "observations_since_learn": 0,
    "last_fired_pipeline_id": None,
    "last_observation_offset": 0,
}


def _read(state_path: str | Path) -> dict:
    path = Path(state_path)
    if not path.exists() or path.stat().st_size == 0:
        return dict(_DEFAULT)
    return {**_DEFAULT, **json.loads(path.read_text())}


def _merge_write(state_path: str | Path, patch: Mapping[str, object]) -> None:
    """Read-merge-write via os.replace so a single write is atomic at the
    filesystem layer.

    Scope of the guarantee: this helper is atomic against ITSELF (two
    Python callers cannot interleave to produce a half-written file).
    It does NOT lock against ``hooks/auto-learn-gate.sh``, which is an
    independent bash writer holding its own ``flock``-based lock
    (``hooks/_lib/learning-flock.sh``). Coordination across the
    Python/bash boundary relies on the bash writer reading and
    preserving every field this helper may have written — see the
    ``LAST_STARTED`` read/write pair in ``hooks/auto-learn-gate.sh``.
    """
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = {**_read(path), **patch}
    payload = json.dumps(merged, sort_keys=True)
    fd, tmp = tempfile.mkstemp(prefix=".learn-state.", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
