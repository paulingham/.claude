"""Stdin->decision CLI for hooks/build-loop-scan.sh.

Reads the PreToolUse Bash payload on stdin, resolves the worktree CWD, runs
`git diff --cached` there, applies the path-scoped fake-marker filter, calls the
pure core for the secret decision, and prints two lines:
  line 1: verdict   (PASSED | FINDINGS | BLOCKED | BYPASSED)
  line 2: categories (comma-joined; empty line when none)

Mirrors hooks/_lib/agentic_security_gate_cli.py: thin adapter, pure core does
the deciding, bypass writes one JSONL ledger record.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from build_loop_scan import (
    decision, is_fake_secret_marker, safe_categories, scan_for_secrets,
)
from harness_paths import harness_data
from log_allowlist_session import sanitize_session

# Staged files whose path sits under one of these segments are fixture/test
# territory: a placeholder-marked line there is suppressed (see is_fake_secret_marker).
_FIXTURE_PATH_SEGMENTS = ("/hooks/tests/", "/fixtures/", "fixtures/", "hooks/tests/")


def _resolve_cwd(payload: dict) -> str:
    """Worktree dir for the staged-diff read: payload .cwd, then env, then PWD."""
    return (
        payload.get("cwd")
        or os.environ.get("CLAUDE_WORKTREE_PATH")
        or os.environ.get("PWD")
        or os.getcwd()
    )


def _staged_diff(cwd: str) -> str:
    """Return staged diff output; '' when nothing staged (exit 0, empty stdout).

    Raises on any error so callers fail-closed:
    - subprocess launch failure (git not found, timeout, bad cwd) → re-raised
    - non-zero git exit (corrupt repo, permission error, etc.) → RuntimeError
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
    except Exception:
        raise  # process-launch failure — fail-closed
    if out.returncode != 0:
        raise RuntimeError(
            f"git diff --cached failed (exit {out.returncode}): {out.stderr.strip()}"
        )
    return out.stdout


def _is_fixture_path(path: str) -> bool:
    return any(seg in path for seg in _FIXTURE_PATH_SEGMENTS)


def _added_lines(diff: str) -> list[str]:
    """Extract added lines from a unified diff, dropping fixture-path placeholders.

    Tracks the current target file (`+++ b/<path>`); added lines (`+`, not `+++`)
    in a fixture/test path are kept only when they carry no placeholder marker.
    """
    kept = []
    current_path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            p = line[4:]
            current_path = (p[2:] if p.startswith("b/") else p).strip()
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        if _is_fixture_path(current_path) and is_fake_secret_marker(added):
            continue
        kept.append(added)
    return kept


def _metrics_dir() -> Path:
    base = os.environ.get("CLAUDE_METRICS_DIR")
    return Path(base) if base else harness_data() / "metrics"


def _write_bypass_ledger(categories: list) -> None:
    """Write one JSONL record to build-loop-scan-bypass.jsonl; never raises."""
    sid = sanitize_session(os.environ.get("CLAUDE_SESSION_ID", "unknown-session"))
    out = _metrics_dir() / sid / "build-loop-scan-bypass.jsonl"
    record = {
        "ts": int(time.time()),
        "session_id": sid,
        "action": "bypass",
        "env_var": "CLAUDE_DISABLE_BUILD_LOOP_SCAN",
        "categories": safe_categories(categories),
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(f"build-loop-scan: bypass ledger write failed: {exc}\n")


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        payload = {}
    disabled = os.environ.get("CLAUDE_DISABLE_BUILD_LOOP_SCAN", "0") == "1"
    added = _added_lines(_staged_diff(_resolve_cwd(payload)))
    secrets = scan_for_secrets("\n".join(added))
    verdict = decision(secrets, 0, 0, disabled)
    if verdict["verdict"] == "BYPASSED":
        _write_bypass_ledger(safe_categories(secrets))
    print(verdict["verdict"])
    print(",".join(safe_categories(verdict["categories"])))


if __name__ == "__main__":
    main()
