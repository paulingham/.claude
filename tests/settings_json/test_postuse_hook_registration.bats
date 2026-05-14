#!/usr/bin/env bats
# Slice B — AC5 (settings.json hook registration)
# Verifies that settings.json:
#   (i)  parses as valid JSON
#   (ii) the PostToolUse no-matcher block contains exactly 5 hooks (was 4)
#   (iii) the new entry's command array references intake-fingerprint-audit.sh
# Resolves MEDIUM-8 by gating the catalog count + entry presence.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SETTINGS="$REPO_ROOT/settings.json"
}

@test "settings.json parses as valid JSON" {
  jq . "$SETTINGS" >/dev/null
}

@test "PostToolUse no-matcher block contains exactly 6 hooks" {
  local count
  count=$(jq '.hooks.PostToolUse[0].hooks | length' "$SETTINGS")
  [ "$count" = "6" ]
}

@test "new entry references intake-fingerprint-audit.sh" {
  jq -r '.hooks.PostToolUse[0].hooks[].args[]?' "$SETTINGS" | grep -q 'intake-fingerprint-audit.sh'
}

@test "intake-fingerprint-audit.sh hook uses bash -lc wrapper" {
  local cmd
  cmd=$(jq -r '.hooks.PostToolUse[0].hooks[4].command' "$SETTINGS")
  [ "$cmd" = "bash" ]
  jq -r '.hooks.PostToolUse[0].hooks[4].args[0]' "$SETTINGS" | grep -q '^-lc$'
}

@test "E4 plan-cache-audit registered as sibling in universal PostToolUse block" {
  # Slice E AC E4 (HIGH-eng-2 verification): plan-cache-audit lives in the
  # SAME no-matcher PostToolUse block as intake-fingerprint-audit. NO new
  # matcher named "Skill" introduced.
  jq -r '.hooks.PostToolUse[0].hooks[].args[]?' "$SETTINGS" | grep -q 'plan-cache-audit.sh'
}

@test "E4b universal PostToolUse block carries no matcher key" {
  # The first PostToolUse block must remain matcherless.
  local has_matcher
  has_matcher=$(jq '.hooks.PostToolUse[0].matcher // empty' "$SETTINGS")
  [ -z "$has_matcher" ]
}

@test "E4c no new PostToolUse matcher named Skill was added" {
  # Walk every PostToolUse block; assert none has matcher == "Skill".
  local skill_blocks
  skill_blocks=$(jq '[.hooks.PostToolUse[] | select(.matcher == "Skill")] | length' "$SETTINGS")
  [ "$skill_blocks" = "0" ]
}

@test "E4d plan-cache-audit.sh hook uses bash -lc wrapper" {
  local cmd
  cmd=$(jq -r '.hooks.PostToolUse[0].hooks[5].command' "$SETTINGS")
  [ "$cmd" = "bash" ]
  jq -r '.hooks.PostToolUse[0].hooks[5].args[0]' "$SETTINGS" | grep -q '^-lc$'
}
