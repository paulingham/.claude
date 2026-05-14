#!/usr/bin/env bats
# Slice A AC-A2 — characterization test that _cf_token reads
# cache_creation_input_tokens from the .usage block with a 0 default.
# The helper is generic over `.usage.<field>` paths (NOT arbitrary JSON paths).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPERS="$REPO_ROOT/hooks/_lib/cost-helpers.sh"
  # shellcheck source=/dev/null
  source "$HELPERS"
}

@test "_cf_token extracts cache_creation_input_tokens from .usage block" {
  local input='{"usage":{"cache_creation_input_tokens":12345}}'
  local got
  got="$(_cf_token "$input" "cache_creation_input_tokens")"
  [ "$got" = "12345" ]
}

@test "_cf_token returns 0 when cache_creation_input_tokens is absent from .usage" {
  local input='{"usage":{"input_tokens":10}}'
  local got
  got="$(_cf_token "$input" "cache_creation_input_tokens")"
  [ "$got" = "0" ]
}

@test "_cf_token returns 0 when .usage block itself is missing" {
  local input='{"subagent_type":"software-engineer"}'
  local got
  got="$(_cf_token "$input" "cache_creation_input_tokens")"
  [ "$got" = "0" ]
}

@test "_cf_token preserves existing field reads (cache_read_input_tokens, input_tokens)" {
  # Round-trip the 3 existing reads to prove we did not regress them.
  local input='{"usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":2000}}'
  [ "$(_cf_token "$input" "input_tokens")" = "1000" ]
  [ "$(_cf_token "$input" "output_tokens")" = "500" ]
  [ "$(_cf_token "$input" "cache_read_input_tokens")" = "2000" ]
}
