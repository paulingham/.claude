#!/usr/bin/env python3
"""Verification-freshness resolver. Path-B advisory — emits decision JSON.

Reads the hook payload from stdin, resolves the freshness verdict by comparing
the recorded `git_head` in `verification-evidence.json` against the worktree
HEAD, and writes one JSON line to stdout:
  line 1: decision -- "SKIP" or "LOG"
  line 2: resolved -- JSON dict (action, reason, staleness_class, heads, ...)

The bash wrapper consumes both lines and emits the JSONL via log-injection.sh.
The wrapper ALWAYS exits 0 — this resolver only computes the would-be verdict.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

GATED_ROLES = {"patch-critic", "product-reviewer", "pr-creation"}
TASK_ID_RE = re.compile(r"^[a-z0-9_-]+$")
try:
    HARD_TTL_SEC = int(os.environ.get("CLAUDE_FRESHNESS_HARD_TTL_SEC", "86400"))
except ValueError:
    HARD_TTL_SEC = 86400


def _emit(decision, resolved):
    sys.stdout.write(f"{decision}\n{json.dumps(resolved)}\n")
    sys.exit(0)


def _skip():
    _emit("SKIP", {})


def _log(action, reason, **extra):
    payload = {"action": action, "reason": reason, **extra}
    _emit("LOG", payload)


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _resolve_worktree(env_path, cwd):
    """Return a worktree dir or None (rule order: env → cwd → None)."""
    for cand in (env_path, cwd):
        if cand and os.path.isdir(cand):
            return cand
    return None


def _worktree_head(worktree):
    """Return the worktree HEAD sha, or special sentinels on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2)
    except subprocess.TimeoutExpired:
        return ("__timeout__", None)
    if result.returncode != 0:
        return (None, None)
    return (result.stdout.strip(), None)


def _load_evidence(path):
    try:
        with open(path) as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, json.JSONDecodeError):
        return None, "parse_error"


def _is_hard_stale(generated_at):
    """True if generated_at is older than HARD_TTL_SEC. Forgiving on parse fail."""
    if not generated_at:
        return False
    try:
        ts = datetime.strptime(
            generated_at.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, TypeError):
        return False
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return age > HARD_TTL_SEC


def _evidence_path(task_id):
    return os.path.join("pipeline-state", task_id, "verification-evidence.json")


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    role = tool_input.get("subagent_type", "")
    if role not in GATED_ROLES:
        _skip()

    task_id = os.environ.get("CLAUDE_PIPELINE_TASK_ID", "unknown")
    if not TASK_ID_RE.fullmatch(task_id):
        _log("would_block", "invalid_task_id")
    worktree = _resolve_worktree(
        os.environ.get("CLAUDE_WORKTREE_PATH"), tool_input.get("cwd"))

    if worktree is None:
        _log("fresh", "no_worktree_resolvable", task_id=task_id)

    path = os.path.join(worktree, _evidence_path(task_id))
    evidence, err = _load_evidence(path)
    if err == "missing":
        # Fallback: evidence may be at the main checkout root (Story B pattern).
        common = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=2)
        if common.returncode == 0:
            root_dir = os.path.dirname(
                os.path.abspath(os.path.join(worktree, common.stdout.strip())))
            if root_dir != worktree:
                root_path = os.path.join(root_dir, _evidence_path(task_id))
                evidence, err = _load_evidence(root_path)
        if err == "missing":
            _log("would_block", "state_file_missing", task_id=task_id)
    if err == "parse_error":
        _log("would_block", "state_file_parse_error", task_id=task_id)

    sandbox = (evidence.get("sandbox_run") or {}).get("status", "")
    if sandbox != "SANDBOX_VERIFIED":
        _log("would_block", "sandbox_staleness", task_id=task_id,
             sandbox_status=sandbox)

    head_result, _ = _worktree_head(worktree)
    if head_result == "__timeout__":
        _log("fresh", "git_timeout", task_id=task_id)
    if head_result is None:
        _log("fresh", "no_worktree_resolvable", task_id=task_id)

    state_head = evidence.get("git_head", "")
    if state_head != head_result:
        _log("would_block", "git_head_mismatch",
             state_file_head=state_head, worktree_head=head_result,
             staleness_class="hard", task_id=task_id,
             tier_results_summary=evidence.get("verdict", ""))

    verdict = evidence.get("verdict", "")
    if not verdict.startswith("VERIFIED"):
        _log("would_block", "verdict_not_verified",
             verdict=verdict, task_id=task_id)

    if _is_hard_stale(evidence.get("generated_at")):
        _log("would_block", "hard_staleness",
             staleness_class="hard", task_id=task_id,
             generated_at=evidence.get("generated_at"))

    _log("fresh", "fresh", task_id=task_id,
         state_file_head=state_head, worktree_head=head_result)


if __name__ == "__main__":
    main()
