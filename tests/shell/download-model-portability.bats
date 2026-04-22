#!/usr/bin/env bats
# Slice 1: download-model.sh must resolve ORT path via detect-ort.sh so
# Linux clones get a .so fallback, not a macOS-only .dylib hardcode.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/skills/embedder/download-model.sh"
}

@test "download-model.sh does not hardcode /opt/homebrew dylib fallback" {
  run grep -F "/opt/homebrew/lib/libonnxruntime.dylib" "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "download-model.sh sources detect-ort.sh to resolve ORT library path" {
  run grep -E "detect-ort\.sh" "$SCRIPT"
  [ "$status" -eq 0 ]
}
