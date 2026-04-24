#!/usr/bin/env bash
# Grouped assertions for Story 3 real case. Functions ≤ 5 lines.

has_patch()     { ls "$1"/golden-diff/*.patch >/dev/null 2>&1; }
nonempty_dir()  { [ -d "$1" ] && [ -n "$(ls -A "$1" 2>/dev/null)" ]; }
no_leak()       { [ -f "$1" ] && ! grep -qE 'golden-diff|\.patch' "$1"; }
meta_synthetic_false() { [ "$(jq -r .synthetic "$1" 2>/dev/null)" = "false" ]; }

check_real_case() {
  local c="$1"
  assert "golden-diff/ contains a .patch file" has_patch "$c"
  assert "context/ is non-empty"               nonempty_dir "$c/context"
  assert "task.md has no oracle leak"          no_leak      "$c/task.md"
  assert "metadata synthetic == false"         meta_synthetic_false "$c/metadata.json"
}
