#!/usr/bin/env bats
# AC8 — vlm-critic-read-guard no-op fast-path benchmark.
# Asserts median wall-clock < 25ms over 100 invocations on the fast-exit path
# (subagent_type != vlm-critic). The fast-path is `grep -F` over raw stdin
# BEFORE jq, exiting 0 immediately when the substring is absent.
#
# Mirror of tests/shell/test_spec_blind_read_guard_perf.bats — the clone is
# soak-safe per plan § 8.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/vlm-critic-read-guard.sh"
  TMP="$(mktemp -d -t vlmcrp.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="vlmcrp-test-$$"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="minimal"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "non_vlm_critic_subagent_fast_path_under_25ms median over 100 invocations" {
  # Payload that does NOT contain the substring "vlm-critic" — triggers the
  # early-exit branch in the hook (fast-substring grep -F BEFORE jq).
  local payload
  payload=$(jq -nc '{tool_name:"Read", subagent_type:"software-engineer", tool_input:{file_path:"/tmp/proj/src/auth.ts"}, session_id:"perf"}')
  echo "$payload" > "$TMP/payload.json"

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
  local median
  median=$(sort -n "$TMP/timings.txt" | sed -n '50p')
  echo "median ms = $median"
  [ "$median" -lt 25 ]
}
