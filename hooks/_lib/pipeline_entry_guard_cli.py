"""Stdin-to-decision CLI for hooks/pipeline-entry-guard.sh.

Reads the PreToolUse Agent payload on stdin, gathers the three pipeline-entry
signals from the environment and filesystem, then prints two lines to stdout:
the gate action and its reason.  Exit code is always 0 — the shell hook
translates the action to an advisory warning or bypass notice.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from log_allowlist_session import sanitize_session
from pipeline_entry_guard import decide
from pipeline_state_paths import find_pipeline_files

_INTAKE_TIER_RE = re.compile(
    r'^\s*(?:tier_emitted|tier):\s*"?(T[0-6])"?\s*$',
    re.MULTILINE,
)


def _pipeline_state_dir() -> str:
    """3-step: HARNESS_DATA > CLAUDE_CONFIG_DIR > ~/.claude, then /pipeline-state."""
    base = (
        os.environ.get("HARNESS_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or str(Path.home() / ".claude")
    )
    return str(Path(base) / "pipeline-state")


def _metrics_dir() -> Path:
    """4-step: CLAUDE_METRICS_DIR > HARNESS_DATA > CLAUDE_CONFIG_DIR > ~/.claude."""
    standalone = os.environ.get("CLAUDE_METRICS_DIR")
    if standalone:
        return Path(standalone)
    config = (
        os.environ.get("HARNESS_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or str(Path.home() / ".claude")
    )
    return Path(config) / "metrics"


def _session_id() -> str:
    return sanitize_session(os.environ.get("CLAUDE_SESSION_ID", "unknown-session"))


def _has_active_pipeline() -> bool:
    """Return True when find_pipeline_files reports at least one active pipeline."""
    try:
        files = find_pipeline_files(Path(_pipeline_state_dir()))
        return bool(files)
    except Exception as exc:
        sys.stderr.write(f"pipeline-entry-guard: find_pipeline_files failed: {exc}\n")
        return False


def _intake_tier(task_id: str) -> str:
    """Extract Tn tier from intake.md for task_id; return '' on any failure."""
    if not task_id:
        return ""
    ws = os.environ.get("CLAUDE_WORKSTREAM", "")
    state_dir = _pipeline_state_dir()
    candidates = []
    if ws:
        candidates.append(
            Path(state_dir) / "workstreams" / ws / task_id / "intake.md"
        )
    candidates.append(Path(state_dir) / task_id / "intake.md")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
            m = _INTAKE_TIER_RE.search(text)
            if m:
                return m.group(1)
        except OSError:
            continue
    return ""


def _write_bypass_ledger(role: str) -> None:
    """Write one JSONL record to pipeline-entry-bypass.jsonl; never raises."""
    sid = _session_id()
    out = _metrics_dir() / sid / "pipeline-entry-bypass.jsonl"
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "bypass",
        "env_var": "CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD",
        "role": role,
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(f"pipeline-entry-guard: bypass ledger write failed: {exc}\n")


def _write_advisory_ledger(role: str, reason: str) -> None:
    """Write one JSONL record to pipeline-entry-advisory.jsonl; never raises."""
    sid = _session_id()
    out = _metrics_dir() / sid / "pipeline-entry-advisory.jsonl"
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "would_block",
        "role": role,
        "reason": reason,
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(f"pipeline-entry-guard: advisory ledger write failed: {exc}\n")


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        data = {}
    tool_input = data.get("tool_input") or {}
    role = tool_input.get("subagent_type") or ""
    task_id = os.environ.get("CLAUDE_PIPELINE_TASK_ID", "")
    disabled = os.environ.get("CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD", "0") == "1"
    ctx = {
        "role": role,
        "task_id": task_id,
        "has_active_pipeline": _has_active_pipeline(),
        "intake_tier": _intake_tier(task_id),
        "disabled": disabled,
    }
    result = decide(ctx)
    if result["action"] == "bypass":
        _write_bypass_ledger(role)
    elif result["action"] == "block":
        _write_advisory_ledger(role, result["reason"])
    print(result["action"])
    print(result["reason"])


if __name__ == "__main__":
    main()
