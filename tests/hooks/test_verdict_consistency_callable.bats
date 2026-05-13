#!/usr/bin/env bats
# Slice A — AC4 (callable)
# Verifies hooks/_lib/verdict-consistency-check.sh behaves as the contract
# specifies — exit 0 when catalog rows ↔ skill frontmatter verdict enums agree
# bidirectionally; exit non-zero with a `missing-in-{catalog,skill}: <verdict>`
# diagnostic when they drift.
#
# The test stages a self-contained CLAUDE_CONFIG_DIR fixture: a minimal catalog
# with a single ROUTING_UPSHIFTED row, plus a plan-self-validation skill whose
# frontmatter declares the same verdict. The three @test cases drive (i) the
# agree path, (ii) drop from skill (missing-in-skill), and (iii) drop from
# catalog (missing-in-catalog).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CALLABLE="$REPO_ROOT/hooks/_lib/verdict-consistency-check.sh"
  TMP_FIXTURE="$(mktemp -d -t verdict-consistency-check-XXXXXX)"
  mkdir -p "$TMP_FIXTURE/rules" "$TMP_FIXTURE/skills/plan-self-validation" "$TMP_FIXTURE/agents"

  # Minimal catalog: header + one row.
  cat > "$TMP_FIXTURE/rules/verdict-catalog.md" <<'EOF'
# Verdict Catalog

## Catalog

| Verdict | Polarity | Emitter skill | Phase | Downstream branch |
|---------|----------|---------------|-------|-------------------|
| `ROUTING_UPSHIFTED` | info | `plan-self-validation` | plan-validation | Plan-phase re-fingerprint detected tier upshift |
EOF

  # Minimal skill: frontmatter declaring the verdict.
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

@test "exits 0 when catalog and skill frontmatter agree" {
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -eq 0 ]
}

@test "exits non-zero with missing-in-skill when skill drops the verdict" {
  cat > "$TMP_FIXTURE/skills/plan-self-validation/SKILL.md" <<'EOF'
---
name: "plan-self-validation"
description: "Test fixture (perturbed: verdict frontmatter removed entirely)"
---

# Plan Self-Validation (fixture)
EOF
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^missing-in-skill: ROUTING_UPSHIFTED$'
}

@test "exits non-zero with missing-in-catalog when catalog drops the row" {
  cat > "$TMP_FIXTURE/rules/verdict-catalog.md" <<'EOF'
# Verdict Catalog

## Catalog

| Verdict | Polarity | Emitter skill | Phase | Downstream branch |
|---------|----------|---------------|-------|-------------------|
EOF
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE '^missing-in-catalog: ROUTING_UPSHIFTED$'
}

@test "diagnostic is single-line" {
  cat > "$TMP_FIXTURE/skills/plan-self-validation/SKILL.md" <<'EOF'
---
name: "plan-self-validation"
description: "Test fixture (perturbed: verdict removed)"
---
EOF
  CLAUDE_CONFIG_DIR="$TMP_FIXTURE" run bash "$CALLABLE"
  [ "$status" -ne 0 ]
  # Output is expected to be exactly one line (single diagnostic).
  local line_count
  line_count=$(printf '%s\n' "$output" | grep -c '^missing-')
  [ "$line_count" -eq 1 ]
}
