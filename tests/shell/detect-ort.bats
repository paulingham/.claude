#!/usr/bin/env bats
# Specs for scripts/_lib/detect-ort.sh — OS-aware ORT library-path resolver.
# Hermetic: tests override ORT_DYLIB_PATH + ORT_CANDIDATE_PATHS so no real
# filesystem probes hit /opt/homebrew or /usr/lib.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

@test "detect_ort returns ORT_DYLIB_PATH when set and file exists" {
  touch "$TMP_DIR/libort.so"
  run bash -c "export ORT_DYLIB_PATH='$TMP_DIR/libort.so'; source '$LIB_DIR/detect-ort.sh'; detect_ort"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP_DIR/libort.so" ]
}

@test "detect_ort ignores ORT_DYLIB_PATH if the file does not exist" {
  run bash -c "export ORT_DYLIB_PATH='$TMP_DIR/missing.so' ORT_CANDIDATE_PATHS=''; source '$LIB_DIR/detect-ort.sh'; detect_ort"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "detect_ort returns first existing candidate from ORT_CANDIDATE_PATHS" {
  touch "$TMP_DIR/second.so"
  local paths="$TMP_DIR/missing.so $TMP_DIR/second.so $TMP_DIR/third.so"
  run bash -c "unset ORT_DYLIB_PATH; export ORT_CANDIDATE_PATHS='$paths'; source '$LIB_DIR/detect-ort.sh'; detect_ort"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP_DIR/second.so" ]
}

@test "detect_ort emits empty output when no candidate exists" {
  run bash -c "unset ORT_DYLIB_PATH; export ORT_CANDIDATE_PATHS='$TMP_DIR/a.so $TMP_DIR/b.so'; source '$LIB_DIR/detect-ort.sh'; detect_ort"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ort_candidates_for_os macos prefers /opt/homebrew before /usr/local" {
  run bash -c "source '$LIB_DIR/detect-ort.sh'; _ort_candidates_for_os macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/opt/homebrew/lib/libonnxruntime.dylib"* ]]
  [[ "$output" == *"/usr/local/lib/libonnxruntime.dylib"* ]]
  [[ "${output%%/usr/local*}" == *"/opt/homebrew"* ]]
}

@test "_ort_candidates_for_os ubuntu lists x86_64-linux-gnu before /usr/local .so" {
  run bash -c "source '$LIB_DIR/detect-ort.sh'; _ort_candidates_for_os ubuntu"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/usr/lib/x86_64-linux-gnu/libonnxruntime.so"* ]]
  [[ "$output" == *"/usr/local/lib/libonnxruntime.so"* ]]
  [[ "${output%%/usr/local*}" == *"/usr/lib/x86_64-linux-gnu"* ]]
}

@test "_ort_candidates_for_os debian yields the same candidate list as ubuntu" {
  run bash -c "source '$LIB_DIR/detect-ort.sh'; _ort_candidates_for_os debian"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/usr/lib/x86_64-linux-gnu/libonnxruntime.so"* ]]
}

@test "_ort_candidates_for_os returns empty for unknown distros" {
  run bash -c "source '$LIB_DIR/detect-ort.sh'; _ort_candidates_for_os alpine"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
