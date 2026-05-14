#!/usr/bin/env python3
"""Append one cache.jsonl record to metrics/{session}/cache.jsonl.

Used by cost-feed.sh (SubagentStop hook) to emit per-spawn cache-token
records for the /cache-audit skill. Uses os.open(O_APPEND|O_CREAT) so
the harness bash-write-guard cannot trip on per-session paths.

Argv (positional):
  1: home_dir            ($HOME at hook invocation time)
  2: session_id          (sanitised)
  3: timestamp           (ISO 8601 UTC)
  4: agent_role
  5: input_tokens        (int)
  6: cache_read_tokens   (int)
  7: cache_create_tokens (int)

All errors are swallowed: this is an advisory log writer for forensic
data, not a control-flow gate.
"""
import json
import os
import sys


def _read_ratio(read, create, inp):
    denom = read + create + inp
    return 0.0 if denom == 0 else read / denom


def _build_record(argv):
    return {
        "ts": argv[3],
        "session_id": argv[2],
        "agent_role": argv[4],
        "input_tokens": int(argv[5]),
        "cache_read_input_tokens": int(argv[6]),
        "cache_creation_input_tokens": int(argv[7]),
        "read_ratio": round(_read_ratio(int(argv[6]), int(argv[7]), int(argv[5])), 6),
    }


def main(argv):
    if len(argv) < 8:
        return 0
    try:
        record = _build_record(argv)
        out_dir = os.path.join(argv[1], ".claude", "metrics", argv[2])
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
