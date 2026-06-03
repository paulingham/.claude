"""JSONL telemetry writers — main ledger + bypass ledger.

`_emit_jsonl` mirrors `hooks/_lib/jsonl-emit.sh` semantics: kwargs-only,
ts auto-stamped, never raises on filesystem failure (AC15).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from harness_paths import harness_data


def _metrics_dir() -> Path:
    base = os.environ.get("CLAUDE_METRICS_DIR")
    if base:
        return Path(base)
    # Precedence: HARNESS_DATA > harness_data() fallback
    return Path(os.environ.get("HARNESS_DATA") or str(harness_data())) / "metrics"


def _session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID", "unknown-session")


def _emit_jsonl(outfile: Path, **fields: Any) -> None:
    """Write one JSONL record. NEVER raises on filesystem failure (AC15)."""
    fields.setdefault("ts", int(time.time()))
    try:
        outfile.parent.mkdir(parents=True, exist_ok=True)
        with outfile.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fields) + "\n")
    except OSError as exc:
        sys.stderr.write(
            f"SAST: failed to write sast-triage JSONL {outfile}: {exc}\n"
        )


def _excerpt(rationale: str) -> str:
    """Single-line, ≤200 chars (AC14)."""
    flat = " ".join(rationale.splitlines()).strip()
    return flat[:200]


def _hash_full(rationale: str) -> str:
    return "sha1:" + hashlib.sha1(rationale.encode("utf-8")).hexdigest()


def write_decision_jsonl(
    *, task_id: str, finding: dict, verdict: str, rationale: str,
) -> None:
    """AC13 — append one record per triage decision."""
    out = _metrics_dir() / _session_id() / "sast-triage.jsonl"
    _emit_jsonl(
        out,
        session_id=_session_id(),
        task_id=task_id,
        rule_id=finding.get("rule_id"),
        tool=finding.get("tool"),
        file=finding.get("file"),
        line=finding.get("line"),
        sast_severity=finding.get("sast_severity"),
        verdict=verdict,
        rationale_excerpt=_excerpt(rationale),
        rationale_full_hash=_hash_full(rationale),
    )


def write_bypass_record(*, task_id: str) -> None:
    """AC20 — distinct bypass ledger; ONE record on bypass."""
    out = _metrics_dir() / _session_id() / "sast-triage-bypass.jsonl"
    _emit_jsonl(
        out,
        session_id=_session_id(),
        task_id=task_id,
        verdict="BYPASSED",
        reason="CLAUDE_DISABLE_SAST_TRIAGE=1",
    )


def write_parse_failed_record(*, task_id: str, failed_rungs: list[dict]) -> None:
    """AC19 — one record on PARSE_FAILED outcome."""
    out = _metrics_dir() / _session_id() / "sast-triage.jsonl"
    _emit_jsonl(
        out,
        session_id=_session_id(),
        task_id=task_id,
        verdict="PARSE_FAILED",
        failed_rungs=failed_rungs,
    )
