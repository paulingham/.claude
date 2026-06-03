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

from harness_paths import harness_data
from log_allowlist_session import sanitize_session
from pipeline_entry_guard import decide
from pipeline_state_paths import find_pipeline_files

_INTAKE_TIER_RE = re.compile(
    r'^\s*(?:tier_emitted|tier):\s*"?(T[0-6])"?\s*$',
    re.MULTILINE,
)
_PATH_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_path_component(value: str) -> str:
    """Allowlist-sanitize a path component; clamp to 64 chars."""
    return _PATH_COMPONENT_RE.sub("_", value)[:64]


def _pipeline_state_dir() -> str:
    """3-step: HARNESS_DATA > harness_data() fallback, then /pipeline-state."""
    base = os.environ.get("HARNESS_DATA") or str(harness_data())
    return str(Path(base) / "pipeline-state")


def _metrics_dir() -> Path:
    """CLAUDE_METRICS_DIR > HARNESS_DATA > harness_data() fallback."""
    standalone = os.environ.get("CLAUDE_METRICS_DIR")
    if standalone:
        return Path(standalone)
    return Path(os.environ.get("HARNESS_DATA") or str(harness_data())) / "metrics"


def _session_id() -> str:
    return sanitize_session(os.environ.get("CLAUDE_SESSION_ID", "unknown-session"))


def _has_active_pipeline() -> bool:
    """Return True when find_pipeline_files reports at least one active pipeline.

    Catches all exceptions intentionally — fail-advisory safety net: any import
    error, OS error, or unexpected failure returns False (no signal), never a crash.
    """
    try:
        files = find_pipeline_files(Path(_pipeline_state_dir()))
        return bool(files)
    except Exception as exc:  # noqa: BLE001 — intentional fail-open
        sys.stderr.write(f"pipeline-entry-guard: find_pipeline_files failed: {exc}\n")
        return False


def _intake_candidates(task_id_safe: str, ws_safe: str, state_dir: Path) -> list:
    """Build ordered list of candidate intake.md paths."""
    candidates = []
    if ws_safe:
        candidates.append(
            state_dir / "workstreams" / ws_safe / task_id_safe / "intake.md"
        )
    candidates.append(state_dir / task_id_safe / "intake.md")
    return candidates


def _parse_tier(path: Path, state_dir: Path) -> str:
    """Read path, return Tn tier string or '' if not found or path escapes state_dir."""
    try:
        resolved = path.resolve()
        resolved.relative_to(state_dir.resolve())  # raises ValueError if outside
        text = path.read_text(encoding="utf-8")
        m = _INTAKE_TIER_RE.search(text)
        return m.group(1) if m else ""
    except (OSError, ValueError):
        return ""


def _intake_tier(task_id: str) -> str:
    """Extract Tn tier from intake.md for task_id; return '' on any failure."""
    if not task_id:
        return ""
    task_id_safe = _sanitize_path_component(task_id)
    ws_safe = _sanitize_path_component(os.environ.get("CLAUDE_WORKSTREAM", ""))
    state_dir = Path(_pipeline_state_dir())
    for path in _intake_candidates(task_id_safe, ws_safe, state_dir):
        tier = _parse_tier(path, state_dir)
        if tier:
            return tier
    return ""


def _write_jsonl_record(path: Path, record: dict) -> None:
    """Append one JSONL record to path; never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(f"pipeline-entry-guard: ledger write failed: {exc}\n")


def _write_bypass_ledger(role: str) -> None:
    """Write one JSONL record to pipeline-entry-bypass.jsonl; never raises."""
    sid = _session_id()
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "bypass",
        "env_var": "CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD",
        "role": role[:128],
    }
    _write_jsonl_record(_metrics_dir() / sid / "pipeline-entry-bypass.jsonl", record)


def _write_advisory_ledger(role: str, reason: str) -> None:
    """Write one JSONL record to pipeline-entry-advisory.jsonl; never raises."""
    sid = _session_id()
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "would_block",
        "role": role[:128],
        "reason": reason,
    }
    _write_jsonl_record(_metrics_dir() / sid / "pipeline-entry-advisory.jsonl", record)


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
