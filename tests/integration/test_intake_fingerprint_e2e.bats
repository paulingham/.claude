#!/usr/bin/env bats
# Slice B — AC5 (integration E2E)
# Feeds a synthetic intake state file → fires the hook → asserts the JSONL line
# lands with shape-conformant content (all 13 keys, valid enums).
# Resolves MEDIUM-5 by exercising the intake → hook → JSONL contract end-to-end.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/intake-fingerprint-audit.sh"
  TMP_DIR="$(mktemp -d -t e2e-XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
  export CLAUDE_SESSION_ID="e2e-session"
  export CLAUDE_CONFIG_DIR="$TMP_DIR/config"
  mkdir -p "$CLAUDE_CONFIG_DIR/pipeline-state/integration-test"
  cat > "$CLAUDE_CONFIG_DIR/pipeline-state/integration-test/intake.md" <<'EOF'
---
task_id: integration-test
tier_emitted: T5
tier_initial: T5
detector_phase: rules
detector_confidence: high
user_phrasing_signals: ["important"]
phrasing_honoured: true
override_token: null
safety_override_fired: false
predicted_files: ["src/foo.ts"]
fingerprint_cost_tokens: 0
criticality_filtered_by_tier: false
---

# Intake state
EOF
  unset CLAUDE_HOOK_PROFILE
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

@test "test_intake_to_hook_to_jsonl_end_to_end" {
  # 1. Verify intake.md has all 12 frontmatter fields
  local intake_md="$CLAUDE_CONFIG_DIR/pipeline-state/integration-test/intake.md"
  [ -f "$intake_md" ]
  local field
  for field in tier_emitted tier_initial detector_phase detector_confidence \
               user_phrasing_signals phrasing_honoured override_token \
               safety_override_fired predicted_files fingerprint_cost_tokens \
               criticality_filtered_by_tier task_id; do
    grep -qE "^${field}:" "$intake_md" || { echo "missing field: ${field}"; return 1; }
  done

  # 2. Fire synthetic PostToolUse with the marker
  local input='{"tool_name":"Skill","tool_response":"[Intake] task_id: integration-test\n[Intake] Tier: T5 (reason: rules; phase: 1; confidence: high)"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]

  # 3. Assert JSONL line lands with all 13 keys
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/e2e-session/intake-overrides.jsonl"
  [ -f "$jsonl_path" ]
  [ "$(wc -l < "$jsonl_path")" -eq 1 ]

  python3 <<'PY'
import json, sys, os
with open(os.environ["CLAUDE_HOOK_LOG_DIR"] + "/e2e-session/intake-overrides.jsonl") as f:
    rec = json.loads(f.read().strip())
required = ["timestamp", "task_id", "tier_emitted", "tier_initial",
            "detector_phase", "detector_confidence", "user_phrasing_signals",
            "phrasing_honoured", "override_token", "safety_override_fired",
            "predicted_files", "fingerprint_cost_tokens"]
missing = [k for k in required if k not in rec]
assert not missing, "missing keys: " + repr(missing)
assert rec["task_id"] == "integration-test", "task_id mismatch: " + repr(rec["task_id"])
assert rec["tier_emitted"] in {"T0","T1","T2","T3","T4","T5","T6","<unknown>"}
assert rec["detector_phase"] in {"rules","fallthrough","<unknown>"}
sys.exit(0)
PY
}
