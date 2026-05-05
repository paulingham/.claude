#!/usr/bin/env bash
# test_best_of_n_skill_structure.sh — single-file structure-drift audit for
# `skills/best-of-n/SKILL.md`. Mirrors `/harness-audit` Step 2c (`STRUCTURE_OK`)
# scoped to one skill so this PR can lock the contract without re-running the
# full harness audit on every change. Pure shell, no helper libs, no fixtures.
#
# Checks:
#   1. SKILL.md exists; tests/ is a directory.
#   2. YAML frontmatter delimited by `---` on line 1 and a later `---`,
#      with required fields: name, description, verdict, phase, dispatch.
#   3. phase ∈ {intake, plan, plan-validation, build, review, final-gate,
#      ship, deploy, reflect, utility}.
#   4. dispatch ∈ {skill-tool, subagent, team}.
#   5. Body has all of: ## When to Invoke, ## Procedure, ## Output, ## Verdict
#      (case-sensitive, exact line match on `^## `).
#   6. Line count ≤ 50 (SKILL.md is a contract, not a tutorial).
#   7. The ## Procedure body is exactly one non-blank line AND that line
#      references `orchestrator/parallel-dispatch-details.md` (delegation).
#   8. All three BoN_* verdicts registered in rules/verdict-catalog.md
#      (backticked form, e.g. `BoN_WINNER_SELECTED`).
#
# Exit 0 + STRUCTURE_OK on success; exit 1 + FAIL: <reason> on any failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL="$REPO_ROOT/skills/best-of-n/SKILL.md"
TESTS_DIR="$REPO_ROOT/skills/best-of-n/tests"
CATALOG="$REPO_ROOT/rules/verdict-catalog.md"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

pass() {
  echo "PASS: $1"
}

# --- Check 1: paths exist ---------------------------------------------------
[[ -f "$SKILL" ]] || fail "skills/best-of-n/SKILL.md not found at $SKILL"
[[ -d "$TESTS_DIR" ]] || fail "skills/best-of-n/tests/ is not a directory at $TESTS_DIR"
pass "SKILL.md and tests/ directory present"

# --- Check 2: frontmatter delimiters + required fields ----------------------
first_line="$(sed -n '1p' "$SKILL")"
[[ "$first_line" == "---" ]] || fail "frontmatter does not open with --- on line 1 (got: $first_line)"

# Find the closing --- on a line >= 2.
fm_close="$(awk 'NR>1 && /^---$/ {print NR; exit}' "$SKILL")"
[[ -n "$fm_close" ]] || fail "frontmatter has no closing --- after line 1"
pass "frontmatter delimited by --- on line 1 and line $fm_close"

fm_block="$(sed -n "2,$((fm_close - 1))p" "$SKILL")"
for field in name description verdict phase dispatch; do
  if ! grep -Eq "^${field}:[[:space:]]" <<<"$fm_block"; then
    fail "frontmatter missing required field: $field"
  fi
done
pass "frontmatter has required fields: name, description, verdict, phase, dispatch"

# Helper: extract scalar value for a top-level frontmatter key.
fm_value() {
  local key="$1"
  grep -E "^${key}:[[:space:]]" <<<"$fm_block" \
    | head -n 1 \
    | sed -E "s/^${key}:[[:space:]]*//" \
    | sed -E 's/^"(.*)"$/\1/' \
    | sed -E "s/^'(.*)'\$/\1/"
}

# --- Check 3: phase value ---------------------------------------------------
phase_val="$(fm_value phase)"
case "$phase_val" in
  intake|plan|plan-validation|build|review|final-gate|ship|deploy|reflect|utility)
    pass "phase value '$phase_val' is in allowed set"
    ;;
  *)
    fail "phase value '$phase_val' not in {intake, plan, plan-validation, build, review, final-gate, ship, deploy, reflect, utility}"
    ;;
esac

# --- Check 4: dispatch value ------------------------------------------------
dispatch_val="$(fm_value dispatch)"
case "$dispatch_val" in
  skill-tool|subagent|team)
    pass "dispatch value '$dispatch_val' is in allowed set"
    ;;
  *)
    fail "dispatch value '$dispatch_val' not in {skill-tool, subagent, team}"
    ;;
esac

# --- Check 5: required body sections ----------------------------------------
required_sections=("## When to Invoke" "## Procedure" "## Output" "## Verdict")
for section in "${required_sections[@]}"; do
  # Exact match on a line beginning with "## " — case-sensitive.
  if ! grep -Fxq "$section" "$SKILL"; then
    fail "missing required section heading: '$section'"
  fi
done
pass "all required sections present: When to Invoke, Procedure, Output, Verdict"

# --- Check 6: line count cap ------------------------------------------------
line_count="$(wc -l <"$SKILL" | tr -d ' ')"
if (( line_count > 50 )); then
  fail "SKILL.md has $line_count lines; cap is 50 (contract, not tutorial)"
fi
pass "SKILL.md line count $line_count ≤ 50"

# --- Check 7: ## Procedure body is one delegation line ----------------------
proc_start="$(grep -n '^## Procedure$' "$SKILL" | head -n 1 | cut -d: -f1)"
[[ -n "$proc_start" ]] || fail "could not locate '## Procedure' line"

# Next `^## ` heading after Procedure.
proc_end="$(awk -v start="$proc_start" 'NR>start && /^## / {print NR; exit}' "$SKILL")"
[[ -n "$proc_end" ]] || fail "no section follows '## Procedure'"

# Body lives strictly between proc_start and proc_end.
proc_body="$(sed -n "$((proc_start + 1)),$((proc_end - 1))p" "$SKILL")"
nonblank_count="$(grep -cE '[^[:space:]]' <<<"$proc_body" || true)"
if (( nonblank_count != 1 )); then
  fail "## Procedure body has $nonblank_count non-blank lines; expected exactly 1 (delegation, not duplicated procedure)"
fi

proc_line="$(grep -E '[^[:space:]]' <<<"$proc_body" | head -n 1)"
if ! grep -Fq 'orchestrator/parallel-dispatch-details.md' <<<"$proc_line"; then
  fail "## Procedure body line does not reference 'orchestrator/parallel-dispatch-details.md' (got: $proc_line)"
fi
pass "## Procedure body is single delegation line referencing orchestrator/parallel-dispatch-details.md"

# --- Check 8: verdicts registered in catalog --------------------------------
[[ -f "$CATALOG" ]] || fail "rules/verdict-catalog.md not found at $CATALOG"
for verdict in BoN_WINNER_SELECTED BoN_FALLBACK_TO_SINGLE BoN_INSUFFICIENT_RESOURCES; do
  if ! grep -Fq "\`${verdict}\`" "$CATALOG"; then
    fail "verdict '$verdict' not registered in rules/verdict-catalog.md (expected backticked form)"
  fi
done
pass "all three BoN_* verdicts registered in verdict-catalog.md"

echo "STRUCTURE_OK"
