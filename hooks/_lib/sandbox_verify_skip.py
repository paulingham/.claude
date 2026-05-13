"""sandbox-verify skill entry points: skip + provision-and-run.

Two public functions:

- `emit_skip_if_no_token(session_id, metrics_dir) -> dict`
  Story-1 contract preserved: missing `E2B_API_KEY` → `SANDBOX_SKIPPED`
  with reason `no-e2b-token` + one JSONL line written. Story 3 hardens
  the JSONL mode to `0o600` (was `0o644`) and guards `session_id` against
  path-traversal via the canonical regex from
  `learning/{hash}/instincts/instinct-path-traversal-bash-vars.md`.

- `provision_and_run(session_id, metrics_dir, test_command,
                     worktree_outcomes, e2b_client) -> dict`
  Story 3 entry point — replaces the Story-1 `SANDBOX_VERIFIED_TBD`
  placeholder. Orchestrates cost-meter starting tick → secrets forwarding
  → provisioning → exec → parse → compare → teardown (guaranteed via
  `try/finally`). Exit paths (happy / parser-raises / hard-cap-trip /
  e2b-unavailable) all converge on `destroy_microvm` exactly once.

JSONL writes use the shared `secure_jsonl.append_secure_jsonl` helper
(`os.open(O_WRONLY|O_CREAT|O_APPEND, 0o600)`) to:
1. Satisfy the bash-write-guard hook that blocks `>>` to `.jsonl`.
2. Harden the file mode to 0o600 (Story-1 security LOW).
"""
from __future__ import annotations

import datetime
import os
import re
import sys
import time
from pathlib import Path

from secure_jsonl import append_secure_jsonl

# Path-traversal guard: canonical regex from
# `instinct-path-traversal-bash-vars.md`. Reject anything outside
# `[A-Za-z0-9_.-]+`. Empty string also rejected.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utc_now_iso8601():
    """ISO-8601 timestamp in UTC, e.g. `2026-05-12T13:45:09Z`."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_session_id(session_id):
    """Reject path-traversal inputs; fall back to `"local"` + stderr warn.

    Canonical sanitiser from `instinct-path-traversal-bash-vars.md`. Any
    input failing the allowlist regex is replaced with `"local"` so the
    JSONL path stays sandboxed under `<metrics_dir>/local/...`.
    """
    if isinstance(session_id, str) and _SESSION_ID_RE.match(session_id):
        return session_id
    sys.stderr.write(
        f"sandbox_verify_skip: rejected session_id {session_id!r} "
        "(path-traversal guard); falling back to 'local'\n")
    return "local"


def emit_skip_if_no_token(session_id, metrics_dir):
    """Story-1 contract: emit SANDBOX_SKIPPED when E2B_API_KEY is missing.

    Story 3 hardenings (no observable contract change for the no-token
    branch):
    - `session_id` runs through `_resolve_session_id` (path-traversal).
    - JSONL is written with mode 0o600 (was 0o644).
    - The token-present branch returns a placeholder; callers route to
      `provision_and_run` directly in Story 3+.
    """
    safe_session_id = _resolve_session_id(session_id)
    token = os.environ.get("E2B_API_KEY", "")
    if token:
        # Story 3+: callers should invoke `provision_and_run` directly when
        # the token is present.
        return {"verdict": "SANDBOX_VERIFIED_TBD",
                "reason": "call-provision-and-run-directly",
                "timestamp": _utc_now_iso8601()}

    timestamp = _utc_now_iso8601()
    record = {"reason": "no-e2b-token", "timestamp": timestamp,
              "session_id": safe_session_id}
    jsonl_path = (Path(metrics_dir) / safe_session_id /
                  "sandbox-verify-skips.jsonl")
    append_secure_jsonl(jsonl_path, record)
    return {"verdict": "SANDBOX_SKIPPED", "reason": "no-e2b-token",
            "timestamp": timestamp}


def _elapsed_seconds_since(start_ts):
    """Wall-clock seconds since `start_ts` (extracted for monkey-patching)."""
    return time.time() - start_ts


def _cost_jsonl_path(metrics_dir, safe_session_id):
    """Build the cost-meter JSONL path under the resolved session dir."""
    return (Path(metrics_dir) / safe_session_id /
            "sandbox-verify-cost.jsonl")


def _skip_jsonl_path(metrics_dir, safe_session_id):
    """Build the skips-log JSONL path under the resolved session dir."""
    return (Path(metrics_dir) / safe_session_id /
            "sandbox-verify-skips.jsonl")


def _emit_skipped(metrics_dir, safe_session_id, reason):
    """Write SANDBOX_SKIPPED line + return verdict envelope."""
    timestamp = _utc_now_iso8601()
    record = {"reason": reason, "timestamp": timestamp,
              "session_id": safe_session_id}
    append_secure_jsonl(_skip_jsonl_path(metrics_dir, safe_session_id), record)
    return {"verdict": "SANDBOX_SKIPPED", "reason": reason,
            "timestamp": timestamp}


def provision_and_run(*, session_id, metrics_dir, test_command,
                      worktree_outcomes, e2b_client,
                      secrets_allowlist=None):
    """Story 3 token-present branch — provision, exec, compare, teardown.

    Procedure (matches plan.md file-touch order):
    1. Cost-meter `starting` tick written BEFORE provisioning
       (state-before-expensive-op).
    2. Provision microVM via injected `e2b_client.provision_microvm`.
    3. Forward only allowlisted env vars (default empty / zero secrets).
    4. Exec `test_command` inside microVM; parse pytest output.
    5. Compare worktree vs sandbox pass sets.
    6. Teardown via `destroy_microvm` in `finally` — guaranteed.
    """
    # Lazy imports keep module import cost low for the no-token path
    # (the most common case in CI without E2B credentials).
    from sandbox_cost_meter import (tick, write_cost_event,
                                    write_starting_tick)
    from sandbox_secrets_allowlist import forward_env
    from sandbox_verify_diff import compare_pass_sets, parse_test_outcomes

    safe_session_id = _resolve_session_id(session_id)
    cost_path = _cost_jsonl_path(metrics_dir, safe_session_id)

    # Step 1: state-before-expensive-op tick.
    write_starting_tick(str(cost_path), session_id=safe_session_id)

    # Step 2: provision.
    provision = e2b_client.provision_microvm()
    if not provision["ok"]:
        # Provision failed (token missing, e2b-unavailable, retry-exhausted).
        return _emit_skipped(metrics_dir, safe_session_id,
                             provision["reason"])

    microvm_id = provision["microvm_id"]
    started_at = provision["started_at"]

    try:
        return _run_and_compare(
            e2b_client=e2b_client,
            microvm_id=microvm_id,
            started_at=started_at,
            test_command=test_command,
            worktree_outcomes=worktree_outcomes,
            secrets_allowlist=secrets_allowlist or [],
            forward_env=forward_env,
            tick=tick,
            parse_test_outcomes=parse_test_outcomes,
            compare_pass_sets=compare_pass_sets,
            cost_path=cost_path,
            safe_session_id=safe_session_id,
            write_cost_event=write_cost_event,
            metrics_dir=metrics_dir,
        )
    finally:
        # Step 6: teardown is ALWAYS attempted, regardless of exit path.
        e2b_client.destroy_microvm(microvm_id)
        write_cost_event(str(cost_path), safe_session_id,
                         event="teardown",
                         payload={"microvm_id": microvm_id})


def _run_and_compare(*, e2b_client, microvm_id, started_at, test_command,
                     worktree_outcomes, secrets_allowlist, forward_env,
                     tick, parse_test_outcomes, compare_pass_sets,
                     cost_path, safe_session_id, write_cost_event,
                     metrics_dir):
    """Inner body of provision_and_run. Extracted to keep `try/finally`
    body cohesive and to make the hard-cap branch testable in isolation."""

    # Hard-cap pre-check: if elapsed time already past the hard threshold
    # (slow provisioning consumed the budget), abort before running tests.
    elapsed = _elapsed_seconds_since(started_at)
    cost_state = tick(elapsed)
    if cost_state["hard_trip"]:
        write_cost_event(str(cost_path), safe_session_id,
                         event="hard-cap-trip",
                         payload={"elapsed_usd": cost_state["elapsed_usd"]})
        return {"verdict": "SANDBOX_FAILED", "reason": "cost-exceeded",
                "diverging_tests": []}

    if cost_state["soft_warn"]:
        write_cost_event(str(cost_path), safe_session_id,
                         event="soft-cap-warn",
                         payload={"elapsed_usd": cost_state["elapsed_usd"]})

    # Forward allowlisted env vars (default empty → zero secrets).
    forwarded = forward_env(secrets_allowlist)

    # Exec inside microVM. RuntimeError / network failures propagate
    # through the `finally` block to guarantee teardown. Network failures
    # that the client catches return {"ok": False, ...}: route to
    # SANDBOX_SKIPPED so worktree-passing tests are not misattributed as
    # diverging (parse_test_outcomes("")={} would yield a false-positive
    # SANDBOX_FAILED with every worktree-pass listed).
    exec_result = e2b_client.exec_in_microvm(
        microvm_id, test_command, env=forwarded)
    if not exec_result.get("ok"):
        return _emit_skipped(metrics_dir, safe_session_id, "e2b-unavailable")
    sandbox_outcomes = parse_test_outcomes(
        exec_result.get("stdout", ""), runner="pytest")
    return compare_pass_sets(worktree_outcomes, sandbox_outcomes)
