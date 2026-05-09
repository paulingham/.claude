#!/usr/bin/env bash
# hook-summary.sh — JSONL telemetry analyzer.
# Reads $CLAUDE_HOOK_LOG_DIR (default: $HOME/.claude/metrics) for **/hooks.jsonl,
# prints slowest hooks, most-frequent errors, and most-frequent enforcement blocks.
# With --anomaly-check, exits 2 if any hook's ERROR rate exceeds threshold
# (fraction, default 0.10) over the last 100 invocations.
#
# Exit-code semantics: exit 2 from a hook means an INTENTIONAL enforcement block
# (no-shell-read, agent-skill-reminder, main-branch-guard, etc. refused a tool
# call by design). Other non-zero codes mean a real hook crash or bug. We track
# them separately so the orchestrator's normal harness-blocked-me events do not
# inflate the anomaly error rate.
#
# Flags: --anomaly-check, --threshold FRAC, --last-n N, --session SID, --hours H.
# Threshold may also be set via CLAUDE_HOOK_ANOMALY_THRESHOLD.
set -uo pipefail

LOG_DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}"
ANOMALY=0
THRESHOLD="${CLAUDE_HOOK_ANOMALY_THRESHOLD:-0.10}"
LAST_N=10; SESSION=""; HOURS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --anomaly-check) ANOMALY=1; shift ;;
    --threshold) THRESHOLD="$2"; shift 2 ;;
    --last-n) LAST_N="$2"; shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --hours) HOURS="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--anomaly-check] [--threshold FRAC] [--last-n N] [--session SID] [--hours H]"; exit 0 ;;
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
threshold = float(os.environ["THRESHOLD"])  # fraction, e.g. 0.10 = 10% error rate
last_n = int(os.environ["LAST_N"])
session = os.environ["SESSION"]
hours = os.environ["HOURS"]
cutoff = time.time() - int(hours) * 3600 if hours else None

pattern = os.path.join(log_dir, session if session else "*", "hooks.jsonl")
files = sorted(glob.glob(pattern))
# Perf path: when --hours is set, skip files whose mtime is older than the
# cutoff before opening them. The mtime check is one stat() per candidate,
# vs. opening + parsing every line. On metrics dirs with thousands of stale
# session subdirs this is the difference between O(n) opens and O(n) stats.
if cutoff is not None:
    fresh_files = []
    for path in files:
        try:
            if os.path.getmtime(path) >= cutoff:
                fresh_files.append(path)
        except OSError:
            continue
    files = fresh_files
durations = defaultdict(list)
exit_codes = defaultdict(list)
errors = defaultdict(int)              # exit_code not in {0, 2}
enforcement_blocks = defaultdict(int)  # exit_code == 2
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
                exit_codes[name].append(ec)
                if ec == 2:
                    enforcement_blocks[name] += 1
                elif ec != 0:
                    errors[name] += 1
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
print("== Most-Frequent Errors (exit_code != 0 and != 2) ==")
if errors:
    err_sorted = sorted(errors.items(), key=lambda kv: -kv[1])[:last_n]
    print("{:<35} {:>8}".format("hook", "errors"))
    for name, n in err_sorted:
        print("{:<35} {:>8}".format(name[:35], n))
else:
    print("(no errors)")

print()
print("== Most-Frequent Enforcement Blocks (exit_code == 2) ==")
if enforcement_blocks:
    blk_sorted = sorted(enforcement_blocks.items(), key=lambda kv: -kv[1])[:last_n]
    print("{:<35} {:>8}".format("hook", "blocks"))
    for name, n in blk_sorted:
        print("{:<35} {:>8}".format(name[:35], n))
else:
    print("(no enforcement blocks)")

if anomaly:
    flagged = []
    block_rates = []
    for name, codes in exit_codes.items():
        window = codes[-100:]   # last 100 invocations
        if not window:
            continue
        err_rate = sum(1 for ec in window if ec not in (0, 2)) / len(window)
        blk_rate = sum(1 for ec in window if ec == 2) / len(window)
        if err_rate > threshold:
            flagged.append((name, err_rate, len(window)))
        if blk_rate > 0:
            block_rates.append((name, blk_rate, len(window)))
    if block_rates:
        print()
        print("== ENFORCEMENT BLOCKS (informational, not anomalous) ==")
        for name, rate, n in sorted(block_rates, key=lambda x: -x[1]):
            blocks = int(round(rate * n))
            print("  {} block_rate={:.0%} ({}/{} invocations)".format(name, rate, blocks, n))
    if flagged:
        print()
        print("== ANOMALY: {} hook(s) exceeded error-rate threshold {:.0%} ==".format(len(flagged), threshold))
        for name, rate, n in sorted(flagged, key=lambda x: -x[1]):
            errs = int(round(rate * n))
            print("  {} error_rate={:.0%} ({}/{} invocations)".format(name, rate, errs, n))
        sys.exit(2)
    else:
        print()
        print("== Anomaly check OK (error-rate threshold {:.0%}) ==".format(threshold))
PY
