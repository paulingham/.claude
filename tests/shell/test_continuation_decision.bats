#!/usr/bin/env bats
# Behavioral tests for hooks/_lib/continuation_decision.py (auto-continue
# discriminator). Pure function, no file I/O, never registered as a hook —
# advisory only, consumed by the orchestrator LLM. Fail-closed contract
# (Iron Law 8): unknown/empty/garbage input must NEVER read as DONE or
# CONTINUE.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DECIDER="$REPO_ROOT/hooks/_lib/continuation_decision.py"
}

decide() {
  python3 "$DECIDER" "$1" "$2"
}

@test "AC8 COMPLETE maps to DONE" {
  run decide "COMPLETE" "false"
  [ "$status" -eq 0 ]
  [ "$output" = "DONE" ]
}

@test "AC9 MISSING with commits present maps to CONTINUE" {
  run decide "MISSING" "true"
  [ "$status" -eq 0 ]
  [ "$output" = "CONTINUE" ]
}

@test "AC10 MISSING with no commits maps to RECOVER" {
  run decide "MISSING" "false"
  [ "$status" -eq 0 ]
  [ "$output" = "RECOVER" ]
}

@test "AC10 CORRUPT with commits present maps to CONTINUE" {
  run decide "CORRUPT" "true"
  [ "$status" -eq 0 ]
  [ "$output" = "CONTINUE" ]
}

@test "AC11 FAILED maps to RECOVER regardless of commits" {
  run decide "FAILED" "false"
  [ "$status" -eq 0 ]
  [ "$output" = "RECOVER" ]

  run decide "FAILED" "true"
  [ "$status" -eq 0 ]
  [ "$output" = "RECOVER" ]
}

# RED-on-revert canary: a legitimately-working agent has not written the
# reader file yet, so this arrives at the discriminator as an unknown or
# empty status. If a future edit defaults unknown status to DONE or
# CONTINUE, this agent's live worktree would be poked/double-dispatched
# mid-run. This test asserts the fail-closed default directly, so a revert
# that reintroduces a fall-through goes RED here even if the mapping rows
# above are individually weakened.
@test "CANARY fail-closed guard: unknown or empty status never yields DONE or CONTINUE" {
  run decide "" "false"
  [ "$status" -eq 0 ]
  [ "$output" = "WAIT" ]

  run decide "garbage-status" "true"
  [ "$status" -eq 0 ]
  [ "$output" = "WAIT" ]
}
