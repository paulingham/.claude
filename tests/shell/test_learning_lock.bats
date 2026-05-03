#!/usr/bin/env bats
# Wave-2 B11.1 — flock-based lock coordination test for learning hooks.
# Bats equivalent of tests/test_learning_lock.py for hosts where bats is preferred.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/learning-flock.sh"
  TMP="$(mktemp -d -t lk.XXXXXX)"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "LK1 lock helper sources cleanly" {
  run bash -c "source $LIB && type with_learning_lock _learning_lock_path"
  [ "$status" -eq 0 ]
}

@test "LK2 lock path matches /tmp/claude-learning-{hash}.lock" {
  run bash -c "source $LIB && _learning_lock_path 'abc123'"
  [ "$status" -eq 0 ]
  [ "$output" = "/tmp/claude-learning-abc123.lock" ]
}

@test "LK3 lock path sanitizes traversal characters" {
  run bash -c "source $LIB && _learning_lock_path '../../etc/passwd'"
  [ "$status" -eq 0 ]
  [ "$output" = "/tmp/claude-learning-....etcpasswd.lock" ]
}

@test "LK4 lock path falls back to 'local' when empty hash" {
  run bash -c "source $LIB && _learning_lock_path ''"
  [ "$status" -eq 0 ]
  [ "$output" = "/tmp/claude-learning-local.lock" ]
}

@test "LK5 disable env-var (CLAUDE_LEARNING_FLOCK_DISABLE=1) falls back to passthrough" {
  CLAUDE_LEARNING_FLOCK_DISABLE=1 run bash -c "source $LIB && _t() { echo ran; }; with_learning_lock 'x' -- _t"
  [ "$status" -eq 0 ]
  [ "$output" = "ran" ]
}

@test "LK6 concurrent invocations on same hash serialize" {
  marker="$TMP/events"
  bash -c "source $LIB && _hold() { date +%s%N >> $marker; sleep 1.5; date +%s%N >> $marker; }; with_learning_lock 'serialize-test' -- _hold" &
  pid=$!
  sleep 0.2
  bash -c "source $LIB && _t() { date +%s%N >> $marker; }; with_learning_lock 'serialize-test' -- _t"
  wait "$pid"
  [ "$(wc -l < "$marker")" -eq 3 ]
  a_start=$(sed -n 1p "$marker")
  a_end=$(sed -n 2p "$marker")
  b_run=$(sed -n 3p "$marker")
  [ "$b_run" -gt "$a_end" ]
  diff=$(( a_end - a_start ))
  [ "$diff" -gt 1000000000 ]
}

@test "LK7 auto-learn-gate.sh sources learning-flock.sh" {
  grep -q 'learning-flock.sh' "$REPO_ROOT/hooks/auto-learn-gate.sh"
  grep -q 'with_learning_lock' "$REPO_ROOT/hooks/auto-learn-gate.sh"
}

@test "LK8 learning-gc.sh sources learning-flock.sh" {
  grep -q 'learning-flock.sh' "$REPO_ROOT/hooks/learning-gc.sh"
  grep -q 'with_learning_lock' "$REPO_ROOT/hooks/learning-gc.sh"
}
