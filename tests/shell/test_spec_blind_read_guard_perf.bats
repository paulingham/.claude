#!/usr/bin/env bats
# AC17 — read-guard no-op fast-path benchmark.
# Asserts median wall-clock < 25ms over 100 invocations on the fast-exit path
# (subagent_type != spec-blind-validator). The fast-path is `grep -F` over raw
# stdin BEFORE jq, exiting 0 immediately when the substring is absent.
#
# Style mirrors tests/shell/test_destructive_verb_block.bats benchmark idiom.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/spec-blind-read-guard.sh"
  TMP="$(mktemp -d -t sbrp.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="sbrp-test-$$"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="minimal"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "SBRP1 read-guard no-op fast-path under 25ms median over 100 invocations" {
  # Payload that does NOT contain the substring "spec-blind-validator"
  # — triggers the early-exit branch.
  local payload
  payload=$(jq -nc '{tool_name:"Read", subagent_type:"software-engineer", tool_input:{file_path:"/tmp/proj/src/auth.ts"}, session_id:"perf"}')
  echo "$payload" > "$TMP/payload.json"

  # Run 100 timed invocations via python — capture wall-clock per-call to a file.
  python3 - "$HOOK" "$TMP/payload.json" "$TMP/timings.txt" <<'PYEOF'
import subprocess, sys, time
hook, payload_file, out = sys.argv[1], sys.argv[2], sys.argv[3]
with open(payload_file, "rb") as f:
    payload = f.read()
times = []
for _ in range(100):
    t0 = time.perf_counter()
    subprocess.run(["bash", hook], input=payload, capture_output=True)
    t1 = time.perf_counter()
    times.append(int((t1 - t0) * 1000))
with open(out, "w") as f:
    for t in times:
        f.write(f"{t}\n")
PYEOF
  # Sort numerically, take 50th-percentile (median of 100 = 50th value).
  local median
  median=$(sort -n "$TMP/timings.txt" | sed -n '50p')
  echo "median ms = $median"
  # Cap at 25ms.
  [ "$median" -lt 25 ]
}
