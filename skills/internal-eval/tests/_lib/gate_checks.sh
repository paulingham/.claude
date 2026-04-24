#!/usr/bin/env bash
# Gate-integration check helpers. Each check ≤ 5 lines.
RULES_DOC="rules/agent-protocol.md"
WORKFLOW="/.github/workflows/internal-eval.yml"
_rules() { echo "$1/$RULES_DOC"; }
_wf()    { echo "$1$WORKFLOW"; }

check_rules_has_gate_section() {
  assert "rules/agent-protocol.md has Internal Eval Gate section" \
    grep -q "^## Internal Eval Gate" "$(_rules "$1")"
}

check_rules_lists_trigger_dirs() {
  local f; f="$(_rules "$1")"
  for d in 'rules/' 'hooks/' 'skills/' 'agents/'; do
    assert "gate section lists $d" grep -qE "\`$d\`" "$f"
  done
}

check_workflow_file_exists() {
  assert "workflow file exists" is_file "$(_wf "$1")"
}

check_workflow_yaml_valid() {
  assert "workflow YAML parses" \
    python3 -c "import sys,yaml; yaml.safe_load(open(sys.argv[1]))" "$(_wf "$1")"
}

check_workflow_pr_label_trigger() {
  local f; f="$(_wf "$1")"
  assert "workflow triggers on pull_request" grep -q "pull_request:" "$f"
  assert "workflow gates on harness-change label" grep -q "harness-change" "$f"
}

check_workflow_invokes_run_suite() {
  assert "workflow invokes run-suite.sh" \
    grep -q "skills/internal-eval/run/run-suite.sh" "$(_wf "$1")"
}

check_workflow_invokes_diff_vs_baseline() {
  assert "workflow invokes diff-vs-baseline.sh" \
    grep -q "skills/internal-eval/score/diff-vs-baseline.sh" "$(_wf "$1")"
}

check_workflow_fails_on_non_eval_passed() {
  local f; f="$(_wf "$1")"
  assert "workflow compares verdict to EVAL_PASSED" grep -q "EVAL_PASSED" "$f"
  assert "workflow exits 1 on non-pass" grep -qE "exit 1" "$f"
}
