"""Observation JSONL parser."""
from __future__ import annotations

import sys
from pathlib import Path

from jsonl_io import iter_jsonl
from models import Observation


def is_pipeline_record(rec: dict) -> bool:
    rt = rec.get("record_type")
    if rt == "pipeline":
        return True
    return rt is None and "pipeline_id" in rec and "phases" in rec


def _require(rec: dict, keys: tuple, lineno: int) -> None:
    for key in keys:
        if key not in rec:
            print(f"SCHEMA_ERROR: missing '{key}' at line {lineno}", file=sys.stderr)
            sys.exit(2)


def _rounds(rec: dict) -> int:
    phases = rec.get("phases") or {}
    review = (phases.get("review") or {}) if isinstance(phases, dict) else {}
    return max(int(review.get("rounds", 1) or 1), 1)


def parse_observation(rec: dict, lineno: int) -> Observation:
    _require(rec, ("pipeline_id", "classification", "phases"), lineno)
    return Observation(
        pipeline_id=str(rec["pipeline_id"]),
        classification=str(rec["classification"]),
        review_rounds=_rounds(rec),
        rework=bool(rec.get("rework", False)),
    )


def read_observations(path: Path) -> dict[str, Observation]:
    out: dict[str, Observation] = {}
    for i, rec in iter_jsonl(path):
        if not is_pipeline_record(rec):
            continue
        obs = parse_observation(rec, i)
        out[obs.pipeline_id] = obs
    return out
