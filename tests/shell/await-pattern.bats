#!/usr/bin/env bats
# await-pattern.sh — orchestrator primitive for log-pattern awaiting.
# Slices: 1=CLI skeleton+args, 2=streaming+ANSI+max_lines, 3=JSONL,
#         4=signal handling, 5=docs.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  AWAIT="$REPO_ROOT/scripts/await-pattern.sh"
  LIB="$REPO_ROOT/scripts/_lib/await-pattern-lib.sh"
  EMIT="$REPO_ROOT/scripts/_lib/await-pattern-emit.sh"
  TMP="$(mktemp -d -t aw.XXXXXX)"
  LOG="$TMP/log.txt"
  : > "$LOG"
  ORIG_HOME="$HOME"
  ORIG_SID="${CLAUDE_SESSION_ID:-}"
  ORIG_TID="${CLAUDE_PIPELINE_TASK_ID:-}"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="aw-test-$$"
  unset CLAUDE_PIPELINE_TASK_ID
}

teardown() {
  pkill -P $$ -f "tail -n +1 -f $LOG" 2>/dev/null || true
  [ -d "$TMP" ] && rm -rf "$TMP"
  export HOME="$ORIG_HOME"
  if [ -n "$ORIG_SID" ]; then export CLAUDE_SESSION_ID="$ORIG_SID"; else unset CLAUDE_SESSION_ID; fi
  if [ -n "$ORIG_TID" ]; then export CLAUDE_PIPELINE_TASK_ID="$ORIG_TID"; else unset CLAUDE_PIPELINE_TASK_ID; fi
}

# ---- SLICE 1: CLI skeleton + arg validation ----

@test "T1 log with 'ready' → exit 0" {
  echo "system ready now" > "$LOG"
  run "$AWAIT" "$LOG" "ready" 5 100
  [ "$status" -eq 0 ]
}

@test "T1b match on line 1 of 100-line pre-populated log → exit 0" {
  { echo "MATCHME"; for i in $(seq 1 99); do echo "line-$i"; done; } > "$LOG"
  run "$AWAIT" "$LOG" "MATCHME" 5 200
  [ "$status" -eq 0 ]
}

@test "T2 0 args → exit 1" {
  run "$AWAIT"
  [ "$status" -eq 1 ]
}

@test "T2b log exists, no match within 1s timeout → exit 124" {
  echo "nothing-here" > "$LOG"
  run "$AWAIT" "$LOG" "ready" 1 100
  [ "$status" -eq 124 ]
}

@test "T3 negative timeout → exit 1" {
  run "$AWAIT" "$LOG" "x" -1 100
  [ "$status" -eq 1 ]
}

@test "T4 non-integer max_lines → exit 1" {
  run "$AWAIT" "$LOG" "x" 5 abc
  [ "$status" -eq 1 ]
}

@test "T9 log_path does not exist → exit 1 within 1s" {
  local missing="$TMP/no-such.log"
  local start end
  start=$(date +%s)
  run "$AWAIT" "$missing" "ready" 30 100
  end=$(date +%s)
  [ "$status" -eq 1 ]
  [ $((end - start)) -lt 2 ]
  echo "$output" | grep -qi "log" || echo "$output" | grep -qi "not found" || echo "$output" | grep -qi "missing"
}

# ---- SLICE 2: Streaming + ANSI + max_lines + watchdog hygiene ----

@test "T5 match on dynamically appended line → exit 0" {
  ( sleep 0.5; echo "ready" >> "$LOG" ) &
  run "$AWAIT" "$LOG" "ready" 5 100
  [ "$status" -eq 0 ]
}

@test "T6 max_lines=10, 15 non-matching lines → exit 1" {
  for i in $(seq 1 15); do echo "noise-$i" >> "$LOG"; done
  run "$AWAIT" "$LOG" "MATCHME" 5 10
  [ "$status" -eq 1 ]
}

@test "ANSI escape stripped before regex match → exit 0" {
  printf '\e[32mtests-green\e[0m\n' > "$LOG"
  run "$AWAIT" "$LOG" "tests-green" 3 50
  [ "$status" -eq 0 ]
}

@test "max_lines counting: 30 ANSI lines + match at 31, max_lines=30 → exit 1" {
  for i in $(seq 1 30); do printf '\e[31mnoise-%d\e[0m\n' "$i" >> "$LOG"; done
  printf '\e[32mtests-green\e[0m\n' >> "$LOG"
  run "$AWAIT" "$LOG" "tests-green" 5 30
  [ "$status" -eq 1 ]
}

@test "max_lines counting: 30 ANSI lines + match at 31, max_lines=31 → exit 0" {
  for i in $(seq 1 30); do printf '\e[31mnoise-%d\e[0m\n' "$i" >> "$LOG"; done
  printf '\e[32mtests-green\e[0m\n' >> "$LOG"
  run "$AWAIT" "$LOG" "tests-green" 5 31
  [ "$status" -eq 0 ]
}

@test "watchdog hygiene: no orphan sleep after match" {
  echo "ready" > "$LOG"
  "$AWAIT" "$LOG" "ready" 30 50 >/dev/null 2>&1
  sleep 0.2
  ! pgrep -P $$ -f "sleep 30" >/dev/null
}

# ---- SLICE 3: JSONL emission ----

_jsonl_path() {
  echo "$HOME/.claude/metrics/$CLAUDE_SESSION_ID/await-events.jsonl"
}

@test "T7 await_match record has all required fields" {
  echo "ready-now" > "$LOG"
  "$AWAIT" "$LOG" "ready" 5 100
  local f; f="$(_jsonl_path)"
  [ -f "$f" ]
  jq -e 'select(.record_type=="await_match")' "$f" >/dev/null
  jq -e '.timestamp' "$f" >/dev/null
  jq -e '.session_id' "$f" >/dev/null
  jq -e '.task_id' "$f" >/dev/null
  jq -e '.log_path' "$f" >/dev/null
  jq -e '.regex' "$f" >/dev/null
  jq -e '.timeout_seconds | type=="number"' "$f" >/dev/null
  jq -e '.elapsed_seconds | type=="number"' "$f" >/dev/null
  jq -e '.matched_line' "$f" >/dev/null
}

@test "T7b matched_line truncated at 512 chars when input is 1000 chars" {
  python3 -c "import sys; sys.stdout.write('x'*999+'M\n')" > "$LOG"
  "$AWAIT" "$LOG" "M" 5 100
  local f; f="$(_jsonl_path)"
  local len; len=$(jq -r '.matched_line | length' "$f")
  [ "$len" -le 512 ]
}

@test "T8 await_timeout record correct fields, matched_line absent" {
  echo "noise" > "$LOG"
  "$AWAIT" "$LOG" "MATCHME" 1 100 || true
  local f; f="$(_jsonl_path)"
  [ -f "$f" ]
  jq -e 'select(.record_type=="await_timeout")' "$f" >/dev/null
  jq -e '.lines_scanned | type=="number"' "$f" >/dev/null
  jq -e 'has("matched_line") | not' "$f" >/dev/null
}

@test "T9b CLAUDE_SESSION_ID unset → file at metrics/local-\$pid/await-events.jsonl" {
  unset CLAUDE_SESSION_ID
  echo "ready" > "$LOG"
  "$AWAIT" "$LOG" "ready" 5 100 >/dev/null 2>&1
  local count
  count=$(find "$HOME/.claude/metrics" -type d -name 'local-*' 2>/dev/null | wc -l | tr -d ' ')
  [ "$count" -ge 1 ]
}

@test "task_id: CLAUDE_PIPELINE_TASK_ID=foo → task_id field is 'foo'" {
  export CLAUDE_PIPELINE_TASK_ID="foo"
  echo "ready" > "$LOG"
  "$AWAIT" "$LOG" "ready" 5 100
  local f; f="$(_jsonl_path)"
  [ "$(jq -r '.task_id' "$f")" = "foo" ]
}

@test "task_id unset → empty string" {
  unset CLAUDE_PIPELINE_TASK_ID
  echo "ready" > "$LOG"
  "$AWAIT" "$LOG" "ready" 5 100
  local f; f="$(_jsonl_path)"
  [ "$(jq -r '.task_id' "$f")" = "" ]
}

@test "jq safety: regex with quote and backslash → fields correct" {
  echo 'value="abc\\def"' > "$LOG"
  "$AWAIT" "$LOG" 'value="abc' 5 100
  local f; f="$(_jsonl_path)"
  [ -f "$f" ]
  jq -e '.regex' "$f" >/dev/null
  jq -e '.matched_line' "$f" >/dev/null
}

# ---- SLICE 4: Signal handling ----

# Signal tests use SIGTERM rather than SIGINT because bash 3.2 (macOS default)
# silently ignores SIGINT for jobs started with & from a shell that has
# SIG_IGN set on SIGINT — once a signal is ignored at shell start, traps cannot
# re-enable it (POSIX rule). The script's INT and TERM traps are wired
# identically so semantics are preserved.

@test "T-INT-1 SIGTERM mid-await → exit 130, one timeout record" {
  echo "noise" > "$LOG"
  "$AWAIT" "$LOG" "MATCHME" 30 1000 >/dev/null 2>&1 &
  local pid=$!
  sleep 0.5
  kill -TERM "$pid" 2>/dev/null
  local status=0
  wait "$pid" || status=$?
  [ "$status" -eq 130 ]
  local f; f="$(_jsonl_path)"
  [ -f "$f" ]
  local n; n=$(grep -c '"record_type":"await_timeout"' "$f")
  [ "$n" -eq 1 ]
}

@test "T-INT-2 after SIGTERM, no orphan tail/grep/sleep" {
  echo "noise" > "$LOG"
  "$AWAIT" "$LOG" "MATCHME" 30 1000 >/dev/null 2>&1 &
  local pid=$!
  sleep 0.5
  kill -TERM "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null || true
  sleep 0.3
  ! pgrep -P "$pid" >/dev/null 2>&1
}

@test "T-INT-3 two rapid SIGTERMs → exactly one JSONL line" {
  echo "noise" > "$LOG"
  "$AWAIT" "$LOG" "MATCHME" 30 1000 >/dev/null 2>&1 &
  local pid=$!
  sleep 0.4
  kill -TERM "$pid" 2>/dev/null
  kill -TERM "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null || true
  local f; f="$(_jsonl_path)"
  [ -f "$f" ]
  local n; n=$(wc -l < "$f" | tr -d ' ')
  [ "$n" -eq 1 ]
}

# ---- SLICE 5: Documentation + shape ----

@test "lib files have header documentation block" {
  head -5 "$LIB" | grep -q '#'
  head -5 "$EMIT" | grep -q '#'
  grep -q 'JSONL\|record_type\|public\|function' "$LIB"
  grep -q 'JSONL\|record_type\|emit' "$EMIT"
}

@test "no-args → usage on stderr" {
  run "$AWAIT"
  [ "$status" -eq 1 ]
  echo "$output" | grep -qi "usage" || echo "$output" | grep -qi "log_path"
}

@test "shape: each script ≤50 lines" {
  [ "$(wc -l < "$AWAIT")" -le 50 ]
  [ "$(wc -l < "$LIB")" -le 50 ]
  [ "$(wc -l < "$EMIT")" -le 50 ]
}

@test "shape: bash -n passes on all 3 files" {
  bash -n "$AWAIT"
  bash -n "$LIB"
  bash -n "$EMIT"
}
