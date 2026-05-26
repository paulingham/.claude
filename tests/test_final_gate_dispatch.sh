#!/usr/bin/env bash
# Structural fixture test for AC4: Final Gate tier-conditional dispatch.
# Tests:
#   1. _qg_extract_intake_tier on T4 fixture returns "T4"
#   2. _qg_extract_intake_tier on T6 fixture returns "T6"
#   3. orchestrator/parallel-dispatch-details.md Final Gate block contains
#      a tier-conditional guard (if.*tier.*T6 pattern)
#   4. spec-blind Agent spawn appears inside T6 conditional guard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB="$REPO_ROOT/hooks/_lib/quality-gate-checks.sh"
DISPATCHER="$REPO_ROOT/orchestrator/parallel-dispatch-details.md"

# shellcheck source=/dev/null
source "$LIB"

assert_eq() {
  local expected="$1" actual="$2" label="$3"
  if [ "$expected" = "$actual" ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (expected='$expected' actual='$actual')" >&2
    exit 1
  fi
}

assert_grep() {
  local pattern="$1" file="$2" label="$3"
  if grep -qE "$pattern" "$file"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (pattern '$pattern' not found in $file)" >&2
    exit 1
  fi
}

# Create temporary fixture intake files
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

T4_INTAKE="$TMP/t4-intake.md"
cat > "$T4_INTAKE" <<'YAML'
---
task_id: test-t4
tier_emitted: T4
budget_total: 5
---
YAML

T6_INTAKE="$TMP/t6-intake.md"
cat > "$T6_INTAKE" <<'YAML'
---
task_id: test-t6
tier_emitted: T6
budget_total: 9
---
YAML

# Test 1: T4 fixture tier extraction
tier_t4="$(_qg_extract_intake_tier "$T4_INTAKE")"
assert_eq "T4" "$tier_t4" "t4_intake_tier_extraction"

# Test 2: T6 fixture tier extraction
tier_t6="$(_qg_extract_intake_tier "$T6_INTAKE")"
assert_eq "T6" "$tier_t6" "t6_intake_tier_extraction"

# Test 3: dispatcher block contains tier-conditional guard for T6
assert_grep "tier.*T6|T6.*tier" "$DISPATCHER" "t4_dispatch_omits_spec_blind (tier-conditional guard present)"

# Test 4: spec-blind Agent spawn appears inside a T6 conditional block
assert_grep "spec-blind" "$DISPATCHER" "t6_dispatch_includes_spec_blind"

# Test 5: spec-blind-validator is structurally inside the T6-conditional block
T6_BLOCK="$(awk '/^\/\/ if \[ "\$tier" = "T6" \]; then$/{found=1} found{print} /^\/\/ fi$/{found=0}' "$DISPATCHER")"
if echo "$T6_BLOCK" | grep -qE 'spec-blind-validator'; then
  echo "PASS: t4_dispatch_spec_blind_is_inside_t6_conditional"
else
  echo "FAIL: t4_dispatch_spec_blind_is_inside_t6_conditional (spec-blind-validator not found in T6 block)" >&2
  exit 1
fi
# Also assert no top-level Agent spawn with spec-blind-validator outside any T6 block
OUTSIDE_BLOCK="$(awk '/^\/\/ if \[ "\$tier" = "T6" \]; then$/{skip=1} skip{if(/^\/\/ fi$/){skip=0}; next} {print}' "$DISPATCHER")"
if echo "$OUTSIDE_BLOCK" | grep -qE 'name:[[:space:]]*"spec-blind-validator"'; then
  echo "FAIL: t4_dispatch_spec_blind_is_inside_t6_conditional (spec-blind-validator found outside T6 block)" >&2
  exit 1
fi

# Test 6: spec-blind Agent spawn (by name field) is inside the T6 conditional block
if echo "$T6_BLOCK" | grep -qE 'name:[[:space:]]*"spec-blind-validator"'; then
  echo "PASS: t6_dispatch_spec_blind_agent_spawn_inside_conditional"
else
  echo "FAIL: t6_dispatch_spec_blind_agent_spawn_inside_conditional (name:\"spec-blind-validator\" not found in T6 block)" >&2
  exit 1
fi

echo "ALL TESTS PASSED"
