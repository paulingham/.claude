#!/usr/bin/env bats
# Slice D — AC D3: skills/pipeline/SKILL.md Step 2c-bis is inserted between
# Step 2c and Step 2d.
# Plan: § Slice slice-d-orchestrator-wiring.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DOC="$REPO_ROOT/skills/pipeline/SKILL.md"
}

@test "D3 Step 2c-bis exists between Step 2c and Step 2d" {
  line_2c="$(grep -n '^### Step 2c:' "$DOC" | head -1 | cut -d: -f1)"
  line_bis="$(grep -n '^### Step 2c-bis:' "$DOC" | head -1 | cut -d: -f1)"
  line_2d="$(grep -n '^### Step 2d:' "$DOC" | head -1 | cut -d: -f1)"
  [ -n "$line_2c" ]
  [ -n "$line_bis" ]
  [ -n "$line_2d" ]
  [ "$line_2c" -lt "$line_bis" ]
  [ "$line_bis" -lt "$line_2d" ]
}

@test "D3b Step 2c-bis references plan-cache-lookup skill" {
  start="$(grep -n '^### Step 2c-bis:' "$DOC" | head -1 | cut -d: -f1)"
  [ -n "$start" ]
  end="$(grep -n '^### Step 2d:' "$DOC" | head -1 | cut -d: -f1)"
  run sed -n "${start},${end}p" "$DOC"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE 'plan-cache-lookup|PLAN_CACHE_(HIT|MISS)'
}
