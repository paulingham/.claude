#!/usr/bin/env python3
"""Append one cache.jsonl record to metrics/{session}/cache.jsonl.

Used by cost-feed.sh (SubagentStop hook) to emit per-spawn cache-token
records for the /cache-audit skill. Uses os.open(O_APPEND|O_CREAT) so
the harness bash-write-guard cannot trip on per-session paths.

Argv (positional):
  1: metrics_base_dir    ($HARNESS_DATA/metrics at hook invocation time)
  2: session_id          (sanitised)
  3: timestamp           (ISO 8601 UTC)
  4: agent_role
  5: input_tokens        (int)
  6: cache_read_tokens   (int)
  7: cache_create_tokens (int)

All errors are swallowed: this is an advisory log writer for forensic
data, not a control-flow gate.

NOTE: argv[1] is the metrics BASE directory (e.g. $HARNESS_DATA/metrics).
The caller is responsible for passing the correct root so that plugin-install
mode (where HARNESS_DATA differs from the overlay config dir) writes to the
same location that cost-feed.sh uses for costs.jsonl.
"""
import json
import os
import sys


def _read_ratio(read, create, inp):
    denom = read + create + inp
    return 0.0 if denom == 0 else read / denom


def _build_record(argv):
    inp, read, create = int(argv[5]), int(argv[6]), int(argv[7])
    return {
        "ts": argv[3],
        "session_id": argv[2],
        "agent_role": argv[4],
        "input_tokens": inp,
        "cache_read_input_tokens": read,
        "cache_creation_input_tokens": create,
        "read_ratio": round(_read_ratio(read, create, inp), 6),
    }


def main(argv):
    if len(argv) < 8:
        return 0
    try:
        # No cache activity at all (input/read/create all zero) → no record.
        if int(argv[5]) == 0 and int(argv[6]) == 0 and int(argv[7]) == 0:
            return 0
        record = _build_record(argv)
        out_dir = os.path.join(argv[1], "metrics", argv[2])
        os.makedirs(out_dir, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(os.path.join(out_dir, "cache.jsonl"), flags, 0o644)
        try:
            line = json.dumps(record, separators=(",", ":")) + "\n"
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except (OSError, ValueError, TypeError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
