#!/usr/bin/env bats
# M2: every hooks/*.sh must run on bash 3.2 (macOS default). This spec greps
# for bash-4+ features and fails if any are found. Pure lint: no network, no
# shell forks, no side effects.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOKS_DIR="$REPO_ROOT/hooks"
}

@test "M2.1 no hook uses associative arrays (declare -A)" {
  run grep -l -E '^[[:space:]]*declare[[:space:]]+-A\b' "$HOOKS_DIR"/*.sh
  [ "$status" -ne 0 ] || { echo "offenders:"; echo "$output"; false; }
}

@test "M2.2 no hook uses readarray or mapfile" {
  run grep -l -E '(^|[^[:alnum:]_])(readarray|mapfile)[[:space:]]' "$HOOKS_DIR"/*.sh
  [ "$status" -ne 0 ] || { echo "offenders:"; echo "$output"; false; }
}

@test "M2.3 no hook uses \${var,,} or \${var^^} case expansion" {
  run grep -l -E '\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^)\}' "$HOOKS_DIR"/*.sh
  [ "$status" -ne 0 ] || { echo "offenders:"; echo "$output"; false; }
}

@test "M2.4 every hook passes bash -n (syntax valid)" {
  for hook in "$HOOKS_DIR"/*.sh; do
    bash -n "$hook" || { echo "syntax error in $hook"; false; }
  done
}
