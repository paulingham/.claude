#!/usr/bin/env bats
# Specs for hooks/_lib/gear-select.sh — Phase A three-gear classifier.
# Default verdict is PAIR (inverted polarity vs the legacy T0-T6 fingerprint,
# which defaults heavy). Escalates to BUILD on feature/multi-file signals,
# to PIPELINE on security/critical signals. One-word NL override wins over
# auto-classification. Fail-safe: any error or empty input -> PIPELINE
# (fail SAFE = fail heavy, never silently drop to light).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/gear-select.sh"
  TMP_DIR="$(mktemp -d)"
  if [[ -n "${HOME+x}" ]]; then
    _PRIOR_HOME_SET=1; _PRIOR_HOME_VAL="$HOME"
  else
    _PRIOR_HOME_SET=0
  fi
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
}

teardown() {
  rm -rf "$TMP_DIR"
  if [[ "$_PRIOR_HOME_SET" = "1" ]]; then
    export HOME="$_PRIOR_HOME_VAL"
  else
    unset HOME
  fi
}

_gear_select_for() {
  local prompt="$1"
  printf '{"prompt": %s}' "$(_json_escape "$prompt")" | bash -c "source '$LIB'; gear_select"
}

_json_escape() {
  # Minimal JSON string quoting for test fixtures (no jq dependency).
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '"%s"' "$s"
}

# --- Default verdict ---------------------------------------------------

@test "G1.1 default verdict is PAIR for a plain conversational prompt" {
  run _gear_select_for "what does this function do"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
}

@test "G1.2 default verdict is PAIR for a small one-line tweak" {
  run _gear_select_for "fix the typo in this comment"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
}

# --- Escalate to BUILD ---------------------------------------------------

@test "G2.1 escalates to BUILD on 'implement' feature signal" {
  run _gear_select_for "implement a new caching layer for the API"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

@test "G2.2 escalates to BUILD on 'build' feature signal" {
  run _gear_select_for "build a new endpoint for user preferences"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

@test "G2.3 escalates to BUILD on 'add' feature signal" {
  run _gear_select_for "add a new component for the dashboard"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

@test "G2.4 escalates to BUILD on multi-file mention" {
  run _gear_select_for "update these three files: foo.rb, bar.rb, and baz.rb"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

# --- Escalate to PIPELINE -------------------------------------------------

@test "G3.1 escalates to PIPELINE on auth signal" {
  run _gear_select_for "implement a new auth flow for the login page"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G3.2 escalates to PIPELINE on payment signal" {
  run _gear_select_for "build the payment webhook handler"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G3.3 escalates to PIPELINE on migration signal even without a feature verb" {
  run _gear_select_for "review the schema migration before we ship"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G3.4 escalates to PIPELINE on plain 'critical' mention" {
  run _gear_select_for "this is a critical fix for the billing system"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

# --- One-word NL override beats auto-classify -----------------------------

@test "G4.1 'just pair' overrides an auth signal down to PAIR" {
  run _gear_select_for "just pair on this auth refactor with me"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
}

@test "G4.2 'pair on this' overrides a multi-file BUILD signal down to PAIR" {
  run _gear_select_for "pair on this, implement the new component across three files"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
}

@test "G4.3 'build it' overrides a plain conversational prompt up to BUILD" {
  run _gear_select_for "build it, this one is simple"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

@test "G4.4 'ship it properly' overrides a plain prompt up to PIPELINE" {
  run _gear_select_for "ship it properly please"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G4.5 'take it all the way' overrides up to PIPELINE" {
  run _gear_select_for "take it all the way on this one"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G4.6 'full pipeline' overrides up to PIPELINE" {
  run _gear_select_for "full pipeline for this change please"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

# --- Fail-safe: empty/malformed input -> PIPELINE --------------------------

@test "G5.1 empty stdin fails safe to PIPELINE" {
  run bash -c "source '$LIB'; printf '' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G5.2 malformed JSON fails safe to PIPELINE" {
  run bash -c "source '$LIB'; printf 'not json at all {{{' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

@test "G5.3 JSON with no prompt key fails safe to PIPELINE" {
  run bash -c "source '$LIB'; printf '{\"other\": \"value\"}' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}

# --- Session state write ----------------------------------------------------

@test "G6.1 gear_select writes the chosen gear to state-dir gear-<PPID>" {
  run bash -c "source '$LIB'; printf '{\"prompt\": \"what does this do\"}' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
  state_file="$HOME/.claude/state/gear-$$"
  # gear_select runs in a subshell under `run bash -c`; the written marker
  # is keyed by that subshell's PPID, which we cannot predict exactly, so
  # assert at least one gear-* file was written with the right content.
  found=0
  for f in "$HOME"/.claude/state/gear-*; do
    [ -e "$f" ] || continue
    if [ "$(cat "$f")" = "PAIR" ]; then
      found=1
    fi
  done
  [ "$found" -eq 1 ]
}

# --- Revert-detection: RED when classifier logic is reverted ---------------

@test "G7.1 revert-detection: BUILD escalation requires the feature-verb regex" {
  # This test intentionally duplicates a subset of G2.* so that reverting
  # the escalate-to-BUILD branch (e.g. hardcoding PAIR) goes RED here too.
  run _gear_select_for "create a new service for notifications"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]
}

@test "G7.2 revert-detection: PIPELINE escalation requires the security-signal regex" {
  run _gear_select_for "rotate the oauth token secret"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
}
