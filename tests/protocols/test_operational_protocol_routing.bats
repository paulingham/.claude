#!/usr/bin/env bats
# Slice A — AC1
# Asserts protocols/operational-protocol.md contains a `## Work-Class Routing
# (Overview)` section between the Fibonacci-removal paragraph (L27 area) and
# `## Error Recovery Principles`, with a 7-row tier table and a source-of-truth
# pointer to protocols/work-class-routing.md.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TARGET="$REPO_ROOT/protocols/operational-protocol.md"
}

@test "operational-protocol.md exists" {
  [ -f "$TARGET" ]
}

@test "Work-Class Routing (Overview) section exists" {
  grep -qE '^## Work-Class Routing \(Overview\)$' "$TARGET"
}

@test "Routing section is positioned BEFORE Error Recovery Principles" {
  local routing_line err_line
  routing_line=$(grep -nE '^## Work-Class Routing \(Overview\)$' "$TARGET" | head -1 | cut -d: -f1)
  err_line=$(grep -nE '^## Error Recovery Principles$' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$routing_line" ]
  [ -n "$err_line" ]
  [ "$routing_line" -lt "$err_line" ]
}

@test "Routing section is positioned AFTER Complexity Budget Thresholds table" {
  local routing_line cb_line
  routing_line=$(grep -nE '^## Work-Class Routing \(Overview\)$' "$TARGET" | head -1 | cut -d: -f1)
  cb_line=$(grep -nE '^### Thresholds$' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$routing_line" ]
  [ -n "$cb_line" ]
  [ "$routing_line" -gt "$cb_line" ]
}

@test "Routing section has the orthogonality paragraph" {
  awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -qE 'orthogonal to (the )?Complexity Budget'
}

@test "Routing section names Step 1.5 Fingerprint" {
  awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -qE 'Step 1\.5'
}

@test "Routing section has exactly 7 tier rows (T0..T6)" {
  local count
  count=$(awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -cE '^\|[[:space:]]*\*\*T[0-6]\*\*')
  [ "$count" -eq 7 ]
}

@test "Routing section has tier T0 row" {
  awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -qE '^\|[[:space:]]*\*\*T0\*\*'
}

@test "Routing section has tier T6 row" {
  awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -qE '^\|[[:space:]]*\*\*T6\*\*'
}

@test "Routing section contains source-of-truth pointer" {
  awk '/^## Work-Class Routing \(Overview\)$/,/^## Error Recovery Principles$/' "$TARGET" \
    | grep -qF 'Source of truth: protocols/work-class-routing.md'
}
