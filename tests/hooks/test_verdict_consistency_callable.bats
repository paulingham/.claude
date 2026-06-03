#!/usr/bin/env bats
# Slice A — AC4 (callable)
# Verifies hooks/_lib/verdict-consistency-check.sh behaves as the contract
# specifies — exit 0 when catalog rows ↔ skill frontmatter verdict enums
# agree bidirectionally with the canonical audit semantics; exit non-zero
# with a single-line diagnostic on drift.
#
# Canonical semantics (per tests/test_verdict_catalog_audit._emitter_resolves):
#   "skill directory containing SKILL.md exists, OR agent file exists" is
#   sufficient resolution. The callable MUST NOT require the skill frontmatter
#   to declare the verdict in its enum.
#
# The test stages a self-contained CLAUDE_CONFIG_DIR fixture: a minimal catalog
# with a single ROUTING_UPSHIFTED row, plus a plan-self-validation skill
# directory whose mere existence resolves the emitter. Drift cases (a) drop
# the skill directory and (b) drop the catalog row.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CALLABLE="$REPO_ROOT/hooks/_lib/verdict-consistency-check.sh"
  TMP_FIXTURE="$(mktemp -d -t verdict-consistency-check-XXXXXX)"
  mkdir -p "$TMP_FIXTURE/protocols" "$TMP_FIXTURE/skills/plan-self-validation" "$TMP_FIXTURE/agents"

  cat > "$TMP_FIXTURE/protocols/verdict-catalog.md" <<'EOF'
# Verdict Catalog

## Catalog

| Verdict | Polarity | Emitter skill | Phase | Downstream branch |
|---------|----------|---------------|-------|-------------------|
| `ROUTING_UPSHIFTED` | info | `plan-self-validation` | plan-validation | Plan-phase re-fingerprint detected tier upshift |
EOF

  cat > "$TMP_FIXTURE/skills/plan-self-validation/SKILL.md" <<'EOF'
---
name: "plan-self-validation"
description: "Test fixture"
verdict: ROUTING_UPSHIFTED
---

# Plan Self-Validation (fixture)
EOF
}

teardown() {
  if [ -n "${TMP_FIXTURE:-}" ] && [ -d "$TMP_FIXTURE" ]; then
    find "$TMP_FIXTURE" -type f -delete
    find "$TMP_FIXTURE" -depth -type d -empty -delete
  fi
}

@test "callable file exists" {
  [ -f "$CALLABLE" ]
}

@test "callable is executable or invokable via bash" {
  bash -n "$CALLABLE"
}

@test "exits 0 when catalog and skill directory agree" {
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -eq 0 ]
}

@test "exits non-zero with missing-in-skill when emitter directory is removed" {
  find "$TMP_FIXTURE/skills/plan-self-validation" -type f -delete
  rmdir "$TMP_FIXTURE/skills/plan-self-validation"
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^missing-in-skill: ROUTING_UPSHIFTED$'
}

@test "exits non-zero with missing-in-catalog when catalog drops the row" {
  cat > "$TMP_FIXTURE/protocols/verdict-catalog.md" <<'EOF'
# Verdict Catalog

## Catalog

| Verdict | Polarity | Emitter skill | Phase | Downstream branch |
|---------|----------|---------------|-------|-------------------|
EOF
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^missing-in-catalog: ROUTING_UPSHIFTED$'
}

@test "diagnostic is single-line on missing-in-skill drift" {
  find "$TMP_FIXTURE/skills/plan-self-validation" -type f -delete
  rmdir "$TMP_FIXTURE/skills/plan-self-validation"
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  local line_count
  line_count=$(printf '%s\n' "$output" | grep -c '^missing-')
  [ "$line_count" -eq 1 ]
}

@test "exits zero against real repo (canonical-semantics smoke)" {
  # Regression guard for round 1 CRITICAL-1: a fork of canonical _emitter_resolves
  # that demanded skill frontmatter declarations would produce 23 false-positive
  # `missing-in-skill:` diagnostics against the live ~/.claude tree. Point the
  # callable at the worktree's own root and assert exit 0 — the canonical audit
  # accepts "skill directory exists" as sufficient.
  CLAUDE_CONFIG_DIR="$REPO_ROOT" run bash "$CALLABLE"
  [ "$status" -eq 0 ]
}

@test "emits error: prefix when config dir is missing" {
  # Regression guard for round 1 MEDIUM-5: a missing config dir is a tooling
  # error, not a catalog/skill drift. Diagnostic prefix must be `error:` so
  # consumers grepping `^missing-in-catalog: [A-Z_]+$` don't confuse it with
  # a real verdict diagnostic.
  CLAUDE_CONFIG_DIR=/nonexistent-config-dir-for-test run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^error: config-dir-not-found$'
  ! echo "$output" | grep -qE '^missing-in-catalog:'
}

@test "emits error: prefix when python helper is missing" {
  # Gap-fill (QA Final Gate): the callable explicitly handles the case where
  # the Python helper alongside it is absent (lines 30-33 of the .sh). No
  # existing test exercises this path. Stage a self-contained copy of the
  # callable in the fixture but omit the helper; assert the `error:`-prefixed
  # diagnostic so consumers don't conflate tooling drift with verdict drift.
  local HELPER_FIXTURE="$TMP_FIXTURE/hooks-no-helper"
  mkdir -p "$HELPER_FIXTURE"
  cp "$CALLABLE" "$HELPER_FIXTURE/verdict-consistency-check.sh"
  # NOTE: deliberately do NOT copy verdict_consistency.py — that is the
  # condition under test.
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$HELPER_FIXTURE/verdict-consistency-check.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^error: helper-not-found$'
  ! echo "$output" | grep -qE '^missing-in-(catalog|skill):'
}
