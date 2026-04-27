#!/usr/bin/env bash
# Shared conformance cases — sourced by the three driver bats files.
# The driver sets BACKEND env + installs CLI shim + sources session-store.sh,
# then runs each case as its own @test in the driver file.

assert_round_trip() {
  local hash="cnf-hash" sid="notes" payload="$BATS_TMPDIR/cnf-payload.md"
  printf 'cnf-blob\n' > "$payload"
  session_store_put "$hash" "$sid" "$payload"
  local got; got=$(session_store_get "$hash" "$sid")
  [ "$got" = "cnf-blob" ]
}

assert_get_miss_exit_1() {
  run session_store_get "no-such-hash" "notes"
  [ "$status" -eq 1 ]
}

assert_delete_then_get_miss() {
  printf 'doomed\n' | session_store_put "del-hash" "notes" -
  session_store_delete "del-hash" "notes"
  run session_store_get "del-hash" "notes"
  [ "$status" -eq 1 ]
}

assert_list_includes_hash() {
  printf 'x' | session_store_put "list-hash" "notes" -
  run session_store_list
  [[ "$output" == *"list-hash"* ]]
}

assert_list_subkeys_emits_headers() {
  printf '# A\n_d_\n# B\n_d_\n' | session_store_put "sk-hash" "notes" -
  local out; out=$(session_store_list_subkeys "sk-hash" "notes")
  [ "$out" = "A
B" ]
}

assert_put_dash_reads_stdin() {
  printf 'piped' | session_store_put "stdin-hash" "notes" -
  local got; got=$(session_store_get "stdin-hash" "notes")
  [ "$got" = "piped" ]
}

assert_empty_blob_round_trip() {
  printf '' | session_store_put "empty-hash" "notes" -
  run session_store_get "empty-hash" "notes"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

assert_section_headers_survive_round_trip() {
  local blob="# Session: Untitled
# Active Work
# Codebase Map"
  printf '%s\n' "$blob" | session_store_put "rt-hash" "notes" -
  local got; got=$(session_store_get "rt-hash" "notes")
  [[ "$got" == *"Session: Untitled"* ]]
  [[ "$got" == *"Active Work"* ]]
  [[ "$got" == *"Codebase Map"* ]]
}

assert_traversal_in_hash_rejected() {
  run session_store_put "../escape" "notes" -
  [ "$status" -ne 0 ]
}

assert_traversal_in_subkey_rejected() {
  run session_store_put "valid-hash" "../escape" -
  [ "$status" -ne 0 ]
}

assert_slash_in_hash_rejected() {
  run session_store_put "ab/cd" "notes" -
  [ "$status" -ne 0 ]
}

assert_leading_dot_in_hash_rejected() {
  run session_store_put ".hidden" "notes" -
  [ "$status" -ne 0 ]
}

assert_empty_hash_rejected() {
  run session_store_put "" "notes" -
  [ "$status" -ne 0 ]
}
