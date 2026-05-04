"""Missing-parent warning emission for agent_parent_chain (C6.2).

Dual-channel: stderr (visible to operator) + JSONL forensic record at
metrics/{session}/parent-chain-warnings.jsonl.
"""
import json
import os
import sys
from pathlib import Path


def _metrics_dir():
    return os.environ.get("CLAUDE_METRICS_DIR") or str(
        Path.home() / ".claude" / "metrics")


def warn_missing_parent(child, missing):
    sys.stderr.write(
        f"parent-chain: {child} -> missing parent '{missing}'\n")
    session = os.environ.get("CLAUDE_SESSION_ID", "no-session")
    out = Path(_metrics_dir()) / session / "parent-chain-warnings.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    record = {"source": "missing-parent", "agent": child, "missing": missing}
    out.open("a").write(json.dumps(record) + "\n")
