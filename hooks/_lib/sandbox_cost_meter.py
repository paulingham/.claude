"""AC5 — per-second cost meter with soft+hard caps for sandbox-verify.

Public API:

- `RATES_USD_PER_SECOND` — module-top dict mirroring the
  `PRICING_PER_MILLION` convention from `cost_estimator.py`. Single source
  of truth; calibrate post-soak once Story 4 surfaces real spend data.
- `tick(elapsed_seconds: float) -> {"soft_warn": bool, "hard_trip": bool,
   "elapsed_usd": float}` — C2 contract.
  Invariant: `hard_trip implies soft_warn`.
- `write_starting_tick(jsonl_path, session_id)` — persists a `starting`
  event BEFORE the first E2B HTTP call, per state-before-expensive-op
  instinct: if the subagent times out mid-provision, the next run sees
  the unfinished tick and can attribute the leak.

Env-var overrides:
- `CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD` (default 0.50)
- `CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD` (default 2.00)

JSONL written via the shared `secure_jsonl.append_secure_jsonl` helper
(`os.open(O_WRONLY|O_CREAT|O_APPEND, 0o600)`) because the bash-write-guard
hook blocks `>>` to `.jsonl` files AND the security LOW from Story 1
mandates 0o600 (was 0o644).
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from secure_jsonl import append_secure_jsonl

# Per-second sandbox cost rate. Placeholder calibration; Story 4 closes the
# loop with real-spend data from `sandbox-verify-cost.jsonl` aggregations.
# E2B microVM list price ~$0.000014 / vCPU-second; we round to $0.0001/s as a
# conservative single-vCPU upper bound that gives the cap shape meaningful
# headroom for the default $0.50 soft / $2.00 hard thresholds.
RATES_USD_PER_SECOND = {
    "default": 0.0001,
}

_DEFAULT_SOFT_USD = 0.50
_DEFAULT_HARD_USD = 2.00


def _read_cap(env_var: str, default: float) -> float:
    """Parse a float env override; fall back to default on any error."""
    raw = os.environ.get(env_var, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _utc_now_iso8601() -> str:
    """ISO-8601 UTC timestamp, matches sandbox_verify_skip._utc_now_iso8601."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def tick(elapsed_seconds: float, rate_key: str = "default") -> dict:
    """Compute cumulative elapsed USD + soft/hard cap state.

    Returns a dict with three required keys (C2 contract):
    - `elapsed_usd`: float — elapsed_seconds * rate.
    - `soft_warn`: bool — True iff elapsed_usd >= soft cap.
    - `hard_trip`: bool — True iff elapsed_usd >= hard cap.

    Invariant: `hard_trip implies soft_warn` (hard >= soft by construction).
    """
    rate = RATES_USD_PER_SECOND.get(rate_key, RATES_USD_PER_SECOND["default"])
    elapsed_usd = float(elapsed_seconds) * rate
    soft_cap = _read_cap("CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD",
                         _DEFAULT_SOFT_USD)
    hard_cap = _read_cap("CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD",
                         _DEFAULT_HARD_USD)
    hard_trip = elapsed_usd >= hard_cap
    # Invariant: hard implies soft. Coerce explicitly to keep the contract.
    soft_warn = elapsed_usd >= soft_cap or hard_trip
    return {"soft_warn": soft_warn, "hard_trip": hard_trip,
            "elapsed_usd": elapsed_usd}


def write_starting_tick(jsonl_path: str, session_id: str) -> None:
    """Persist a `starting` event BEFORE the first E2B HTTP call.

    The starting tick is the forensic breadcrumb that lets `/forensics` (and
    Story 4 skip-rate aggregator) detect leaked microVMs: a starting tick
    with no matching teardown record means the subagent was killed mid-run.
    """
    record = {
        "event": "starting",
        "session_id": session_id,
        "timestamp": _utc_now_iso8601(),
    }
    append_secure_jsonl(Path(jsonl_path), record)


def write_cost_event(jsonl_path: str, session_id: str,
                     event: str, payload: dict) -> None:
    """Generic cost-event JSONL writer (teardown, soft-warn, hard-trip)."""
    record = {
        "event": event,
        "session_id": session_id,
        "timestamp": _utc_now_iso8601(),
        **payload,
    }
    append_secure_jsonl(Path(jsonl_path), record)
