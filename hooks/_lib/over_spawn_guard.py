"""Over-spawn guard — advisory phase fan-out scorer.

Reads a PreToolUse Agent stdin JSON payload, infers the spawn's pipeline
phase from the prompt text, increments a per-session/per-task/per-phase
counter, and appends a JSONL warning when spawn_count exceeds the
slice-count-aware ceiling.

INVARIANT 1: stdout is ALWAYS empty — no modified_tool_input ever emitted.
INVARIANT 2: exit 0 ALWAYS — never blocks an Agent spawn.

enforces: protocols/autonomous-intelligence.md — advisory-first
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------------------------------------------- constants

_ROLE_TO_PHASE: dict[str, str] = {
    "patch-critic": "final-gate",
    "spec-blind-validator": "final-gate",
    "product-reviewer": "final-gate",
    "qa-engineer": "final-gate",
    "code-reviewer": "review",
    "security-engineer": "review",
    "software-engineer": "build",
    "frontend-engineer": "build",
    "database-engineer": "build",
    "infrastructure-engineer": "build",
    "fix-engineer": "build",
    "pbt-engineer": "build",
    "sandbox-verify-engineer": "build",
}

_ROLE_RE = re.compile(r"agents/([a-z][a-z0-9-]+)\.md")


# ----------------------------------------------------------------- public API


def infer_phase(prompt: str, subagent_type: str = "") -> str | None:
    """Infer the pipeline phase from a spawn prompt.

    Regex-scans prompt for `agents/<role>.md` marker (present on every
    dispatch per CLAUDE.md § Dispatch). Falls back to subagent_type when
    the prompt marker is absent (documented-unreliable per runtime-guard-key.sh).
    Returns None for unrecognised roles so the guard stays silent.
    """
    match = _ROLE_RE.search(prompt)
    role = match.group(1) if match else subagent_type.strip()
    return _ROLE_TO_PHASE.get(role)


def ceiling_for(phase: str, slice_count: int) -> float:
    """Return the agent-spawn ceiling for a phase given slice_count.

    build      -> max(slice_count, 1)
    review     -> max(2, ceil(slice_count / 2))
    final-gate -> max(1, ceil(slice_count / 2))
    other      -> math.inf  (never warn)

    Uses math.ceil intentionally — floor would produce ceiling 0 on 1-slice
    final-gate which causes every gate agent to warn spuriously.
    """
    if phase == "build":
        return max(slice_count, 1)
    if phase == "review":
        return max(2, math.ceil(slice_count / 2))
    if phase == "final-gate":
        return max(1, math.ceil(slice_count / 2))
    return math.inf


def resolve_slice_count(state_dir: str) -> tuple[str | None, int | None]:
    """Find the active task and return (task_id, slice_count).

    Greps pipeline-state for `verdict: in_progress` (mirrors
    runtime-guard-respawn.sh:9-15 idiom). Parses the plan via
    plan_dag_resolver.parse_plan; v1/missing → slice_count=1 (correct
    for a single-slice task — NOT silent). Returns (None, None) when
    no active pipeline exists.
    """
    task_id = _active_task_id(state_dir)
    if not task_id:
        return (None, None)

    plan_path = os.path.join(state_dir, task_id, "plan.md")
    try:
        from plan_dag_resolver import parse_plan
        result = parse_plan(plan_path)
        if hasattr(result, "slices"):
            return (task_id, max(1, len(result.slices)))
        return (task_id, 1)
    except Exception:
        return (task_id, None)


def counter_path(metrics_dir: str, session_id: str, task_id: str, phase: str) -> str:
    """Return the per-session/task/phase counter file path.

    Keyed on session_id + task_id + phase to prevent cross-pipeline bleed
    (mirrors _rg_compute_respawn_key which hashes stype|tid).
    """
    return os.path.join(metrics_dir, session_id, "over-spawn", f"{task_id}--{phase}.count")


def bump_counter(path: str) -> int:
    """Read→increment→write the counter at path. Returns the new count.

    Mirrors _rg_increment_respawn from runtime-guard-respawn.sh:28-35.
    Creates parent directories as needed.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    current = 0
    if os.path.isfile(path):
        raw = Path(path).read_text().strip()
        if raw.isdigit():
            current = int(raw)
    current += 1
    Path(path).write_text(str(current))
    return current


def build_record(
    phase: str,
    spawn_count: int,
    ceiling: float,
    slice_count: int,
    task_id: str,
) -> dict:
    """Build a JSONL warning record (6 mandatory fields + ts)."""
    return {
        "phase": phase,
        "spawn_count": spawn_count,
        "ceiling": ceiling,
        "slice_count": slice_count,
        "task_id": task_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    """Entry point called by pre-agent-over-spawn-guard.sh.

    Reads JSON from stdin, scores the spawn, writes a JSONL warn record.
    All output goes to JSONL only — stdout is kept silent (INVARIANT 1).
    Never raises to caller: all exceptions are swallowed (INVARIANT 2).
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return

    try:
        _score(payload)
    except Exception:
        return


# ----------------------------------------------------------------- internals


def _safe_component(s: str | None) -> str:
    """Strip all chars except [A-Za-z0-9_-] — mirrors session-id.sh:34.

    Removes dots and slashes, so `../../x` → `x` (cannot escape a metrics dir).
    Returns empty string for None or all-unsafe input.
    """
    return re.sub(r"[^A-Za-z0-9_-]", "", s or "")


def _active_task_id(state_dir: str) -> str | None:
    """Find the active task_id by grepping for `verdict: in_progress`.

    Returns the task_id from the sorted-first matching file so that the result
    is deterministic when more than one in-progress pipeline exists.
    """
    if not os.path.isdir(state_dir):
        return None
    try:
        import subprocess
        result = subprocess.run(
            ["grep", "-rl", "verdict: in_progress", state_dir],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:
        return None
    if not lines:
        return None
    matched_file = sorted(lines)[0]
    try:
        for line in Path(matched_file).read_text().splitlines():
            if line.startswith("task_id:"):
                return _safe_component(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return None


def _score(payload: dict) -> None:
    """Core scoring logic — raises on any error (caught by main)."""
    tool_input = (payload or {}).get("tool_input") or {}
    prompt = str(tool_input.get("prompt") or "")
    subagent_type = str(tool_input.get("subagent_type") or "")
    session_id = _safe_component((payload or {}).get("session_id"))

    phase = infer_phase(prompt, subagent_type)
    if phase is None:
        return

    harness_data = os.environ.get(
        "HARNESS_DATA",
        os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude"))
    )
    metrics_dir = os.path.join(harness_data, "metrics")
    state_dir = os.path.join(harness_data, "pipeline-state")

    task_id, slice_count = resolve_slice_count(state_dir)
    if task_id is None or slice_count is None:
        return

    cpath = counter_path(metrics_dir, session_id, task_id, phase)
    spawn_count = bump_counter(cpath)
    ceiling = ceiling_for(phase, slice_count)

    if spawn_count <= ceiling:
        return

    from secure_jsonl import append_secure_jsonl
    jsonl_path = Path(metrics_dir) / session_id / "over-spawn-warnings.jsonl"
    record = build_record(phase, spawn_count, ceiling, slice_count, task_id)
    append_secure_jsonl(jsonl_path, record)


if __name__ == "__main__":
    main()
