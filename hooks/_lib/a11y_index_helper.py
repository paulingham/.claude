"""Index.json writer used by the design-qc capture step.

Node owns capture; this helper is the Python-side seam available to
tests and to any Python tool that needs to assemble an index from
already-normalised per-snapshot JSON files.
"""
from __future__ import annotations

import json
from pathlib import Path

INDEX_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1


def write_index(
    index_path: str | Path,
    *,
    task_id: str,
    captured_at: str,
    build_status: str,
    server_started: bool,
    routes: list[dict],
    a11y_global: dict,
) -> dict:
    """Write index.json with required schema_version and shape. Returns the dict."""
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "task_id": task_id,
        "captured_at": captured_at,
        "build_status": build_status,
        "server_started": server_started,
        "routes": list(routes),
        "a11y_global": dict(a11y_global),
    }
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    Path(index_path).write_text(json.dumps(payload, sort_keys=True))
    return payload
