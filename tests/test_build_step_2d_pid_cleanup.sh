#!/usr/bin/env bash
# Security HIGH-5 — Step 2d MUST use SIGKILL-safe process-group cleanup.
# Assertions: SKILL.md Step 2d sub-step 5 uses setsid, persists DEV_PID to
# pipeline-state/{task-id}/.dev-server.pid, and traps EXIT with the process-group
# form kill -- -$DEV_PID. Reflect-phase reap note present.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test build_step_2d_pid_cleanup"

assert "SKILL.md Step 2d uses setsid for dev server" \
  grep -qF "setsid npm run dev" "$SKILL"

assert "SKILL.md Step 2d writes PID to .dev-server.pid" \
  grep -qF '.dev-server.pid' "$SKILL"

assert "SKILL.md Step 2d trap uses process-group kill form" \
  grep -qF 'kill -- -$DEV_PID' "$SKILL"

assert "SKILL.md Step 2d notes Reflect-phase reap of stale PID files" \
  grep -qF "Reflect phase reaps stale" "$SKILL"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
