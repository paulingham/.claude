#!/usr/bin/env bash
# Safe JSONL emission helper. Avoids shell-into-Python interpolation —
# values pass via argv (sys.argv) so quotes/newlines in values cannot
# break JSON or trigger Python syntax errors.

_jsonl_emit() {
  # Usage: _jsonl_emit <outfile> <key1> <val1> [<key2> <val2> ...]
  local outfile="$1"; shift
  python3 - "$@" >> "$outfile" <<'PY'
import json, sys, time
args = sys.argv[1:]
d = {args[i]: args[i + 1] for i in range(0, len(args) - 1, 2)}
d["ts"] = int(time.time())
print(json.dumps(d))
PY
}
