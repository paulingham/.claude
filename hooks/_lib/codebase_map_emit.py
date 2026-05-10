"""Forensic JSONL emitter for codebase-map hooks.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice C AC19:
emits one JSONL line per rebuild attempt to
`metrics/{session-id}/codebase-map-rebuild.jsonl` with the contract
fields `(ts, file_count, time_ms, cache_hit_rate, sha_before,
sha_after, hook)`.

Why a dedicated helper, not bash printf
=======================================

Per memory `instinct-jsonl-log-injection-printf`, dynamic values
(timestamps, SHAs, file counts) formatted via bash `printf '%s'` can
break JSON when content contains quotes, backslashes, or control
characters. This helper round-trips through `json.dumps()` for
guaranteed-valid output. Sibling pattern: `hooks/_lib/log-injection.sh`
uses the same Python-json approach for the thinking-defaults schema;
that helper is hard-coded to its own field set, so we ship a separate
emitter for the codebase-map schema.

CLI form
========

The bash hook invokes us as:

    python3 hooks/_lib/codebase_map_emit.py \
        --metrics-file PATH \
        --hook rebuild|poll \
        --file-count N \
        --time-ms N \
        --cache-hit-rate F \
        --sha-before SHA \
        --sha-after SHA

We append the line atomically (open in 'a' mode is atomic for small
writes on POSIX with O_APPEND).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_FIELDS = (
    "ts",
    "file_count",
    "time_ms",
    "cache_hit_rate",
    "sha_before",
    "sha_after",
    "hook",
)


def build_record(
    file_count: int,
    time_ms: int,
    cache_hit_rate: float,
    sha_before: str,
    sha_after: str,
    hook: str,
    ts: str | None = None,
) -> str:
    """Build one JSONL line from named arguments. Returns the line string."""
    record = {
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "file_count": int(file_count),
        "time_ms": int(time_ms),
        "cache_hit_rate": float(cache_hit_rate),
        "sha_before": str(sha_before),
        "sha_after": str(sha_after),
        "hook": str(hook),
    }
    return json.dumps(record)


def append_record(metrics_file: Path, record_line: str) -> None:
    """Append one record line to the JSONL file (creates parents)."""
    metrics_file = Path(metrics_file)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    with metrics_file.open("a") as fh:
        fh.write(record_line + "\n")


def _cli_main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-file", required=True, type=Path)
    parser.add_argument("--hook", required=True)
    parser.add_argument("--file-count", required=True, type=int)
    parser.add_argument("--time-ms", required=True, type=int)
    parser.add_argument(
        "--cache-hit-rate", required=True, type=float
    )
    parser.add_argument("--sha-before", required=True)
    parser.add_argument("--sha-after", required=True)
    args = parser.parse_args(argv)
    line = build_record(
        file_count=args.file_count,
        time_ms=args.time_ms,
        cache_hit_rate=args.cache_hit_rate,
        sha_before=args.sha_before,
        sha_after=args.sha_after,
        hook=args.hook,
    )
    append_record(args.metrics_file, line)
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main(sys.argv[1:]))
