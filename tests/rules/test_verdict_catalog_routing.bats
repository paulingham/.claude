#!/usr/bin/env bats
# Slice A — AC4 (rows + Notes)
# Asserts rules/verdict-catalog.md (a) contains a `ROUTING_UPSHIFTED` row with
# the correct shape and emitter, (b) the row is positioned after `PLAN_HOLES`
# and before `BUILD_COMPLETE`, (c) the `ROUTED` row carries the `tier: T0..T6`
# payload addendum, and (d) the Notes section documents the tier field.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TARGET="$REPO_ROOT/rules/verdict-catalog.md"
}

@test "verdict-catalog.md exists" {
  [ -f "$TARGET" ]
}

@test "ROUTING_UPSHIFTED row exists with correct shape" {
  grep -qE '^\| `ROUTING_UPSHIFTED` \| info \| `plan-self-validation` \| plan-validation \|' "$TARGET"
}

@test "ROUTING_UPSHIFTED row appears exactly once" {
  local count
  count=$(grep -cE '^\| `ROUTING_UPSHIFTED` \| info \| `plan-self-validation` \| plan-validation \|' "$TARGET")
  [ "$count" -eq 1 ]
}

@test "ROUTING_UPSHIFTED row is positioned AFTER PLAN_HOLES" {
  local upshift_line holes_line
  upshift_line=$(grep -nE '^\| `ROUTING_UPSHIFTED`' "$TARGET" | head -1 | cut -d: -f1)
  holes_line=$(grep -nE '^\| `PLAN_HOLES`' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$upshift_line" ]
  [ -n "$holes_line" ]
  [ "$upshift_line" -gt "$holes_line" ]
}

@test "ROUTING_UPSHIFTED row is positioned BEFORE BUILD_COMPLETE" {
  local upshift_line build_line
  upshift_line=$(grep -nE '^\| `ROUTING_UPSHIFTED`' "$TARGET" | head -1 | cut -d: -f1)
  build_line=$(grep -nE '^\| `BUILD_COMPLETE`' "$TARGET" | head -1 | cut -d: -f1)
  [ -n "$upshift_line" ]
  [ -n "$build_line" ]
  [ "$upshift_line" -lt "$build_line" ]
}

@test "ROUTING_UPSHIFTED row references the spec" {
  grep -E '^\| `ROUTING_UPSHIFTED`' "$TARGET" \
    | grep -qF 'protocols/work-class-routing.md'
}

@test "ROUTED row carries the tier T0..T6 payload addendum" {
  grep -E '^\| `ROUTED`' "$TARGET" | grep -qE 'tier: T0\.\.T6'
}

@test "Notes section contains a bullet documenting the tier field on ROUTED" {
  awk '/^## Notes$/,EOF' "$TARGET" \
    | grep -qE '^- `ROUTED` carries a `tier:'
}

@test "Notes-section bullet references the Step 1.5 fingerprint" {
  awk '/^## Notes$/,EOF' "$TARGET" \
    | grep -E '^- `ROUTED` carries a `tier:' \
    | grep -qF 'Step 1.5'
}
