"""GP-K1 — auto-learn Stop-gate decision, state-advance, and re-entrancy lock.

Subsumes the bash helpers auto-learn-gate-core.sh (gate predicate + trigger
banner), auto-learn-state.sh (observation counting + state I/O), and
auto-learn-lock.sh (in-process lock). The thin wrapper hooks/auto-learn-gate.sh
resolves paths and holds the cross-process flock, then hands off here.

State I/O reuses learn_status._read / _merge_write so a patch-merge over the
on-disk document preserves last_learn_started (the B8.1 sentinel) structurally —
build_patch deliberately omits that key so the merge never strips it.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import learn_status

_OBS_FLOOR = 3
_PIPE_FLOOR = 3
_STALE_HOURS = 24
_ROTATE_BYTES = 1048576
_PARSE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_CLI = Path(__file__).resolve().parent / "pipeline_state_paths_cli.py"

_TRIGGER_RULE = "═══════════════════════════════════════════════════════"


def hours_since(ts: str | None) -> int:
    """Whole hours since an ISO-8601 UTC timestamp; null/blank/garbage → 999."""
    then = _parse_utc(ts)
    if then is None:
        return 999
    return int((datetime.now(timezone.utc) - then).total_seconds() // 3600)


def _parse_utc(ts: str | None) -> datetime | None:
    """Strict ISO-8601 UTC parse; None for blank/null/unparseable input."""
    try:
        return datetime.strptime(ts or "", _PARSE_FORMAT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def current_pipeline_id() -> str:
    """First in_progress pipeline's task_id via the shared DUAL_PATH CLI."""
    data = os.environ.get("HARNESS_DATA") or str(Path.home() / ".claude")
    env = {**os.environ, "PSP_DIR": f"{data}/pipeline-state"}
    files = _run_find(env)
    active = next((f for f in files if "in_progress" in _read_text(f)), "")
    return _first_task_id(active) if active else ""


def _run_find(env: dict) -> list[str]:
    """Shell to pipeline_state_paths_cli.py find; one path per output line."""
    proc = subprocess.run([sys.executable, str(_CLI), "find"], env=env,
                          capture_output=True, text=True)
    return [line for line in proc.stdout.splitlines() if line]


def _read_text(path: str) -> str:
    """File contents, or empty string when the path is unreadable."""
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def _first_task_id(path: str) -> str:
    """The value of the first `task_id:` frontmatter line, else empty."""
    for line in _read_text(path).splitlines():
        if line.startswith("task_id:"):
            return line.split(":", 1)[1].strip()
    return ""


def count_new_pipeline_ids(obs: str, offset: int) -> list[str]:
    """pipeline_id of each pipeline record appended past `offset`."""
    return [rec.get("pipeline_id", "unknown")
            for rec in _records_after(obs, offset)
            if _is_pipeline_record(rec)]


def _records_after(obs: str, offset: int) -> list[dict]:
    """JSON records decoded from `obs` after `offset`; bad lines skipped."""
    raw = _read_bytes(obs)[offset:]
    parsed = (_parse_line(line) for line in raw.splitlines() if line.strip())
    return [rec for rec in parsed if rec is not None]


def _parse_line(line: bytes) -> dict | None:
    # WHY: jq 2>/dev/null in the bash predecessor silently dropped malformed
    # lines — one corrupt observation must not abort the whole gate count.
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None


def _read_bytes(obs: str) -> bytes:
    """Raw bytes of the observations file, or empty when absent."""
    try:
        return Path(obs).read_bytes()
    except OSError:
        return b""


def _is_pipeline_record(rec: dict) -> bool:
    """A record counts as a pipeline when typed or shaped like one."""
    if rec.get("record_type") == "pipeline":
        return True
    return "pipeline_id" in rec and "phases" in rec \
        and rec.get("record_type", "") != "tool_use"


def latest_pipeline_id(ids: list[str]) -> str:
    """The most recent pipeline id, or empty when there were none."""
    return ids[-1] if ids else ""


def file_size(path: str) -> int:
    """Byte size of a file, or 0 when it does not exist."""
    return os.path.getsize(path) if os.path.exists(path) else 0


def should_fire(obs, pipes, last_run, cur, fired) -> bool:
    """Gate predicate: obs floor, then a staleness dimension, then dedupe."""
    if obs < _OBS_FLOOR:
        return False
    if not (pipes >= _PIPE_FLOOR or _no_recent_run(last_run)):
        return False
    return not (cur and cur == fired)


def _no_recent_run(last_run: str | None) -> bool:
    """True when no /learn has run recently enough to suppress the gate."""
    return last_run in (None, "", "null") or hours_since(last_run) >= _STALE_HOURS


def print_trigger(obs: int, pipes: int) -> None:
    """Emit the /learn trigger banner on stdout (verbatim contract)."""
    print(_TRIGGER_RULE)
    print(f"[auto-learn-gate] Triggered: {obs} observations, "
          f"{pipes} pipelines since last /learn")
    print("Invoke /learn now to extract instincts before continuing.")
    print(_TRIGGER_RULE)


def rotate(log: str) -> None:
    """Roll the gate log to `.1` once it grows past 1 MiB."""
    if file_size(log) > _ROTATE_BYTES:
        os.replace(log, f"{log}.1")


def log_not_met(log: str, obs: int, pipes: int, last_run: str | None) -> None:
    """Append a gate=not-met line, rotating an over-large log first."""
    rotate(log)
    with open(log, "a") as handle:
        handle.write(f"[auto-learn-gate] obs={obs} pipelines={pipes} "
                     f"last_run={last_run} gate=not-met\n")


def evaluate(state: dict, obs: str) -> dict:
    """PURE: derive the advanced counters and current/last pipeline ids."""
    offset = state.get("last_observation_offset") or 0
    new_ids = count_new_pipeline_ids(obs, offset)
    latest = latest_pipeline_id(new_ids)
    cur = current_pipeline_id() or latest
    return _assemble(state, new_ids, latest, cur, file_size(obs))


def _assemble(state, new_ids, latest, cur, new_size) -> dict:
    """Combine on-disk counters with the freshly-counted observation delta."""
    fired = state.get("last_fired_pipeline_id") or ""
    obs_count = (state.get("observations_since_learn") or 0) + len(new_ids)
    pipes = (state.get("pipelines_since_learn") or 0) + _pipe_delta(new_ids, latest, fired)
    return {"obs": obs_count, "pipes": pipes, "latest": latest, "cur": cur, "fired": fired,
            "last_run": state.get("last_learn_run"), "new_size": new_size}


def _pipe_delta(new_ids: list[str], latest: str, fired: str) -> int:
    """Bump pipelines-since-learn by one for a fresh, not-yet-fired pipeline."""
    return 1 if new_ids and latest and latest != fired else 0


def decide(ev: dict, log: str) -> str:
    """Fire (print trigger, claim cur) or record not-met; return next fired."""
    if should_fire(ev["obs"], ev["pipes"], ev["last_run"], ev["cur"], ev["fired"]):
        print_trigger(ev["obs"], ev["pipes"])
        return ev["cur"] or ev["fired"]
    log_not_met(log, ev["obs"], ev["pipes"], ev["last_run"])
    return ev["fired"]


def build_patch(ev: dict, fired: str) -> dict:
    """Gate-owned fields only — NOT last_learn_started (merge preserves it)."""
    return {"last_learn_run": ev["last_run"],
            "pipelines_since_learn": ev["pipes"],
            "observations_since_learn": ev["obs"],
            "last_fired_pipeline_id": fired or None,
            "last_observation_offset": ev["new_size"]}


def run(state: str, obs: str, log: str) -> None:
    """Lock the sidecar, evaluate the gate, then merge-write the advance."""
    with _lock(state):
        ev = evaluate(learn_status._read(state), obs)
        fired = decide(ev, log)
        learn_status._merge_write(state, build_patch(ev, fired))


@contextlib.contextmanager
def _lock(state: str):
    handle = _acquire(f"{state}.lock")
    try:
        yield
    finally:
        handle.close()


def _acquire(sidecar: str):
    # WHY: flock the `.lock` SIDECAR — _merge_write's os.replace swaps the state
    # file's inode, so a lock held on the state file itself would protect nothing.
    handle = open(sidecar, "w")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def main(argv: list[str]) -> int:
    """argv entry: --state/--obs/--log, run the gate, exit 0."""
    args = _parse_args(argv[1:])
    run(args.state, args.obs, args.log)
    return 0


def _parse_args(argv: list[str]):
    """Parse the three required path flags into a namespace."""
    parser = argparse.ArgumentParser()
    for flag in ("--state", "--obs", "--log"):
        parser.add_argument(flag, required=True)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
