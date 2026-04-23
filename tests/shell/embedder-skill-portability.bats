#!/usr/bin/env bats
# L3: skills/embedder/SKILL.md documents both macOS and Linux install paths
# for ONNX Runtime. Guards against future edits that reintroduce an
# unbalanced, brew-only install hint.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SKILL="$REPO_ROOT/skills/embedder/SKILL.md"
}

@test "L3.4 embedder SKILL has a Linux setup subsection" {
  run grep -cE '^### Linux' "$SKILL"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}

@test "L3.5 embedder Requirements mentions apt-based Linux ORT install" {
  req="$(awk '/^## Requirements$/{f=1;next} f && /^## /{f=0} f' "$SKILL")"
  echo "$req" | grep -q 'libonnxruntime-dev'
}

@test "L3.6 embedder Requirements mentions macOS brew install" {
  req="$(awk '/^## Requirements$/{f=1;next} f && /^## /{f=0} f' "$SKILL")"
  echo "$req" | grep -q 'brew install'
}
