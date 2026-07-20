#!/usr/bin/env bash
# Structural fixture test for AC4: Final Gate gear-conditional dispatch.
# Tests:
#   1. _qg_extract_intake_gear on BUILD fixture returns "BUILD"
#   2. _qg_extract_intake_gear on PIPELINE fixture returns "PIPELINE"
#   3. orchestrator/parallel-dispatch-details.md Final Gate block contains
#      a gear-conditional guard (if.*gear.*PIPELINE pattern)
#   4. spec-blind Agent spawn appears inside PIPELINE conditional guard
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

BUILD_INTAKE="$TMP/build-intake.md"
cat > "$BUILD_INTAKE" <<'YAML'
---
task_id: test-build
gear_emitted: BUILD
budget_total: 5
---
YAML

PIPELINE_INTAKE="$TMP/pipeline-intake.md"
cat > "$PIPELINE_INTAKE" <<'YAML'
---
task_id: test-pipeline
gear_emitted: PIPELINE
budget_total: 9
---
YAML

# Test 1: BUILD fixture gear extraction
gear_build="$(_qg_extract_intake_gear "$BUILD_INTAKE")"
assert_eq "BUILD" "$gear_build" "build_intake_gear_extraction"

# Test 2: PIPELINE fixture gear extraction
gear_pipeline="$(_qg_extract_intake_gear "$PIPELINE_INTAKE")"
assert_eq "PIPELINE" "$gear_pipeline" "pipeline_intake_gear_extraction"

# Test 3: dispatcher block contains gear-conditional guard for PIPELINE
assert_grep "gear.*PIPELINE|PIPELINE.*gear" "$DISPATCHER" "build_dispatch_omits_spec_blind (gear-conditional guard present)"

# Test 4: spec-blind Agent spawn appears inside a PIPELINE conditional block
assert_grep "spec-blind" "$DISPATCHER" "pipeline_dispatch_includes_spec_blind"

# Test 5: spec-blind-validator is structurally inside the PIPELINE-conditional block
PIPELINE_BLOCK="$(awk '/^\/\/ if \[ "\$gear" = "PIPELINE" \]; then$/{found=1} found{print} /^\/\/ fi$/{found=0}' "$DISPATCHER")"
if echo "$PIPELINE_BLOCK" | grep -qE 'spec-blind-validator'; then
  echo "PASS: build_dispatch_spec_blind_is_inside_pipeline_conditional"
else
  echo "FAIL: build_dispatch_spec_blind_is_inside_pipeline_conditional (spec-blind-validator not found in PIPELINE block)" >&2
  exit 1
fi
# Also assert no top-level Agent spawn with spec-blind-validator outside any PIPELINE block
OUTSIDE_BLOCK="$(awk '/^\/\/ if \[ "\$gear" = "PIPELINE" \]; then$/{skip=1} skip{if(/^\/\/ fi$/){skip=0}; next} {print}' "$DISPATCHER")"
if echo "$OUTSIDE_BLOCK" | grep -qE 'name:[[:space:]]*"spec-blind-validator"'; then
  echo "FAIL: build_dispatch_spec_blind_is_inside_pipeline_conditional (spec-blind-validator found outside PIPELINE block)" >&2
  exit 1
fi

# Test 6: spec-blind Agent spawn (by name field) is inside the PIPELINE conditional block
if echo "$PIPELINE_BLOCK" | grep -qE 'name:[[:space:]]*"spec-blind-validator"'; then
  echo "PASS: pipeline_dispatch_spec_blind_agent_spawn_inside_conditional"
else
  echo "FAIL: pipeline_dispatch_spec_blind_agent_spawn_inside_conditional (name:\"spec-blind-validator\" not found in PIPELINE block)" >&2
  exit 1
fi

echo "ALL TESTS PASSED"
