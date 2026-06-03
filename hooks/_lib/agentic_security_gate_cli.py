"""Stdin->decision CLI for hooks/agentic-security-gate.sh.

Reads the PreToolUse Agent payload on stdin, resolves the branch changeset via
git, and prints two lines: the gate action and its reason.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from agentic_security_gate import gate_decision
from harness_paths import harness_data
from log_allowlist_session import sanitize_session


def _changed_files():
    """Return files changed vs main...HEAD; fall back to HEAD if no main ref."""
    primary = ["git", "diff", "--name-only", "main...HEAD"]
    fallback = ["git", "diff", "--name-only", "HEAD"]
    for cmd in (primary, fallback):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            continue
        if out.returncode == 0:
            return sorted(line for line in out.stdout.splitlines() if line.strip())
    return []


def _metrics_dir() -> Path:
    base = os.environ.get("CLAUDE_METRICS_DIR")
    if base:
        return Path(base)
    return harness_data() / "metrics"


def _session_id() -> str:
    return sanitize_session(os.environ.get("CLAUDE_SESSION_ID", "unknown-session"))


def _write_bypass_ledger(surfaces: list) -> None:
    """Write one JSONL record to agentic-gate-bypass.jsonl; never raises."""
    sid = _session_id()
    out = _metrics_dir() / sid / "agentic-gate-bypass.jsonl"
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "bypass",
        "env_var": "CLAUDE_DISABLE_AGENTIC_GATE",
        "surfaces": surfaces,
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(f"agentic-security-gate: bypass ledger write failed: {exc}\n")


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        data = {}
    tool_input = data.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type") or ""
    prompt = tool_input.get("prompt") or ""
    disabled = os.environ.get("CLAUDE_DISABLE_AGENTIC_GATE", "0") == "1"
    decision = gate_decision(
        _changed_files(), prompt, subagent_type=subagent_type, disabled=disabled
    )
    if decision["action"] == "bypass":
        _write_bypass_ledger(decision["surfaces"])
    print(decision["action"])
    print(decision["reason"])


if __name__ == "__main__":
    main()
