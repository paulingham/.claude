#!/usr/bin/env bats
# B8.2 — eval-capture-on-merge.sh must fully detach the worker.
#
# Asserts:
#   D1. Hook returns within a bounded time (<2000ms) even when the worker
#       sleeps for many seconds — proving stdout/stderr are redirected,
#       the worker is backgrounded with `&`, AND it is detached with
#       `disown` so the parent shell does not wait.
#   D2. After the hook exits, a sentinel proves the worker process is
#       still alive (i.e. it was actually spawned and survives the hook's
#       exit). This guards against the "hook just exits without spawning"
#       false-positive.
#   D3. With CLAUDE_EVAL_CAPTURE_NOFORK=1 (test hook) the hook runs the
#       worker synchronously — sanity check that the synchronous branch
#       still works as documented.
#
# Test design: we copy the hook + dispatcher into a tmp dir and replace
# the worker with a stub that writes a "started" sentinel, sleeps 5s, then
# writes a "finished" sentinel. The hook is invoked with a fake
# `gh pr merge 999` payload + privacy-ack env. Timing measures the hook's
# wall-clock duration.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK/hooks/_lib"

  # Copy the production hook + dispatcher verbatim. HERE_ECM resolves
  # relative to the hook's own location, so the dispatcher and worker
  # must sit in $WORK/hooks/_lib/.
  cp "$REPO_ROOT/hooks/eval-capture-on-merge.sh" "$WORK/hooks/eval-capture-on-merge.sh"
  cp "$REPO_ROOT/hooks/_lib/eval-capture-dispatch.sh" "$WORK/hooks/_lib/eval-capture-dispatch.sh"

  # Stub worker: write a started sentinel, sleep 5s, write finished sentinel.
  # If the hook is synchronous, the hook's own duration will exceed 5s.
  # If detached, the hook returns quickly and the finished sentinel
  # appears later (asynchronously).
  cat > "$WORK/hooks/_lib/eval-capture-worker.sh" <<SH
#!/usr/bin/env bash
echo started > "$WORK/started"
sleep 5
echo finished > "$WORK/finished"
SH
  chmod +x "$WORK/hooks/_lib/eval-capture-worker.sh"

  # CLAUDE_CONFIG_DIR points at REPO_ROOT so the hook finds the real
  # log.sh. log.sh is no-oped via CLAUDE_HOOK_LOG_ENABLED=0 to keep the
  # test isolated (no metrics writes).
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_LOG_ENABLED=0
  export CLAUDE_EVAL_CAPTURE_ACKED=1
  unset CLAUDE_EVAL_CAPTURE_NOFORK
}

teardown() {
  unset CLAUDE_CONFIG_DIR CLAUDE_HOOK_LOG_ENABLED CLAUDE_EVAL_CAPTURE_ACKED \
        CLAUDE_EVAL_CAPTURE_NOFORK
  # Clean any lingering worker processes the test spawned.
  pkill -f "$WORK/hooks/_lib/eval-capture-worker.sh" 2>/dev/null || true
}

_run_hook_timed() {
  # Echo a payload that the dispatcher will parse as `gh pr merge 999`.
  local payload
  payload=$(jq -nc '{tool_input:{command:"gh pr merge 999 --squash"}}')
  local t0_ns t1_ns
  t0_ns=$(python3 -c 'import time; print(int(time.time()*1000))')
  echo "$payload" | bash "$WORK/hooks/eval-capture-on-merge.sh"
  t1_ns=$(python3 -c 'import time; print(int(time.time()*1000))')
  HOOK_DURATION_MS=$(( t1_ns - t0_ns ))
}

@test "D1 hook returns within 2000ms even when worker sleeps 5s (detachment)" {
  _run_hook_timed
  echo "hook duration: ${HOOK_DURATION_MS}ms"
  [ "$HOOK_DURATION_MS" -lt 2000 ]
}

@test "D2 worker sentinel exists after hook exits (worker actually spawned)" {
  _run_hook_timed
  # Give the detached worker a moment to write the started sentinel.
  # 1s is plenty — bash + echo is ~milliseconds.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -f "$WORK/started" ] && break
    sleep 0.1
  done
  [ -f "$WORK/started" ]
  # finished sentinel should NOT exist yet (worker still in sleep 5s);
  # if it does, the worker ran synchronously inline somehow.
  [ ! -f "$WORK/finished" ]
}

@test "D3 CLAUDE_EVAL_CAPTURE_NOFORK=1 runs worker synchronously (sanity check)" {
  export CLAUDE_EVAL_CAPTURE_NOFORK=1
  # With NOFORK + a 5s sleep stub the hook would block ≥5s; replace the
  # stub with an instant version to keep this test fast.
  cat > "$WORK/hooks/_lib/eval-capture-worker.sh" <<SH
#!/usr/bin/env bash
echo synchronous > "$WORK/sync_marker"
SH
  chmod +x "$WORK/hooks/_lib/eval-capture-worker.sh"
  _run_hook_timed
  # Synchronous path: marker MUST exist by the time the hook returns.
  [ -f "$WORK/sync_marker" ]
}
