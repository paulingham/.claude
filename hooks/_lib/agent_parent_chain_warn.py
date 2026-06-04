"""Missing-parent warning emission for agent_parent_chain (C6.2).

Dual-channel: stderr (visible to operator) + JSONL forensic record at
metrics/{session}/parent-chain-warnings.jsonl.
"""
import json
import os
import sys
from pathlib import Path

from harness_paths import harness_data, resolved_harness_data

_O_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)


def _metrics_dir():
    base = os.environ.get("CLAUDE_METRICS_DIR")
    if base:
        return base
    # Precedence: HARNESS_DATA env > harness_data() resolver fallback
    return str(Path(resolved_harness_data()) / "metrics")


def warn_missing_parent(child, missing):
    sys.stderr.write(
        f"parent-chain: {child} -> missing parent '{missing}'\n")
    session = os.environ.get("CLAUDE_SESSION_ID", "no-session")
    out = Path(_metrics_dir()) / session / "parent-chain-warnings.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    record = {"source": "missing-parent", "agent": child, "missing": missing}
    fd = os.open(str(out), _O_FLAGS, 0o644)
    with os.fdopen(fd, "a") as fh:
        fh.write(json.dumps(record) + "\n")
