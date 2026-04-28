#!/usr/bin/env bash
# hook-summary.sh — JSONL telemetry analyzer.
# Reads $CLAUDE_HOOK_LOG_DIR (default: $HOME/.claude/metrics) for **/hooks.jsonl,
# prints slowest hooks + most-frequent failures. With --anomaly-check, exits 2
# if any hook breaches threshold. Flags: --anomaly-check, --threshold MS,
# --last-n N, --session SID, --hours H.
set -uo pipefail

LOG_DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}"
ANOMALY=0; THRESHOLD=100; LAST_N=10; SESSION=""; HOURS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --anomaly-check) ANOMALY=1; shift ;;
    --threshold) THRESHOLD="$2"; shift 2 ;;
    --last-n) LAST_N="$2"; shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--anomaly-check] [--threshold MS] [--last-n N] [--session SID] [--hours H]"; exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

ANOMALY="$ANOMALY" THRESHOLD="$THRESHOLD" LAST_N="$LAST_N" \
SESSION="$SESSION" HOURS="$HOURS" LOG_DIR="$LOG_DIR" \
python3 - <<'PY'
import json, os, sys, glob, time
from collections import defaultdict

log_dir = os.environ["LOG_DIR"]
anomaly = os.environ["ANOMALY"] == "1"
threshold = int(os.environ["THRESHOLD"])
last_n = int(os.environ["LAST_N"])
session = os.environ["SESSION"]
hours = os.environ["HOURS"]
cutoff = time.time() - int(hours) * 3600 if hours else None

pattern = os.path.join(log_dir, session if session else "*", "hooks.jsonl")
files = sorted(glob.glob(pattern))
durations = defaultdict(list)
failures = defaultdict(int)
total = 0

for path in files:
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cutoff:
                    ts = rec.get("timestamp", "")
                    try:
                        rec_t = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
                    except ValueError:
                        continue
                    if rec_t < cutoff:
                        continue
                name = rec.get("hook_name", "unknown")
                dur = rec.get("duration_ms", 0)
                ec = rec.get("exit_code", 0)
                durations[name].append(dur)
                if ec != 0:
                    failures[name] += 1
                total += 1
    except OSError:
        continue

if total == 0:
    print("No hook telemetry found in", log_dir)
    sys.exit(0)

# Slowest hooks (by max duration)
slowest = sorted(durations.items(), key=lambda kv: -max(kv[1]))[:last_n]
print("== Slowest Hooks (max duration_ms, top {}) ==".format(last_n))
print("{:<35} {:>8} {:>8} {:>6}".format("hook", "max_ms", "avg_ms", "calls"))
for name, durs in slowest:
    avg = sum(durs) // len(durs)
    print("{:<35} {:>8} {:>8} {:>6}".format(name[:35], max(durs), avg, len(durs)))

print()
print("== Most-Frequent Failures (exit_code != 0) ==")
if failures:
    fail_sorted = sorted(failures.items(), key=lambda kv: -kv[1])[:last_n]
    print("{:<35} {:>8}".format("hook", "fails"))
    for name, n in fail_sorted:
        print("{:<35} {:>8}".format(name[:35], n))
else:
    print("(no failures)")

if anomaly:
    over = [(n, max(d)) for n, d in durations.items() if max(d) > threshold]
    if over:
        print()
        print("== ANOMALY: {} hook(s) exceeded threshold {}ms ==".format(len(over), threshold))
        for name, mx in sorted(over, key=lambda kv: -kv[1]):
            print("  {} max={}ms".format(name, mx))
        sys.exit(2)
    else:
        print()
        print("== Anomaly check OK (threshold {}ms) ==".format(threshold))
PY
