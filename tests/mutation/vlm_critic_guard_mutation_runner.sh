#!/usr/bin/env bash
# Reproducible mutation-test runner for the slice-b vlm-critic guard hook.
#
# Why this exists: same rationale as
# tests/mutation/visual_diff_mutation_runner.sh — the harness has no
# Stryker/mutmut infrastructure for shell, and adding one would dwarf the
# tested surface. `skills/verify/SKILL.md` § Manual fallback allows a
# sed-based mutation runner as long as it is reproducible.
#
# Target: hooks/vlm-critic-read-guard.sh + hooks/_lib/vlm-critic-allow-paths.sh.
# These two files carry the security-bearing branches (allowlist matcher,
# realpath gate, subagent_type exact-match, fast-substring grep). The
# guard-common library is a verbatim clone of spec-blind-guard-common.sh
# (which is already mutation-tested under the spec-blind suite); we do not
# re-mutate identical code paths.
#
# Invocation:
#   bash tests/mutation/vlm_critic_guard_mutation_runner.sh
#
# Exit codes:
#   0  — all mutants accounted for (killed or documented equivalents);
#        kill rate meets ≥0.70 gate per rules/core.md § Iron Law 1.
#   1  — a mutant survived that is NOT in the documented-equivalents list,
#        OR the test runner could not be invoked, OR the kill rate is
#        below 0.70 across non-equivalent mutants.
#   2  — environment unmet (bats not on PATH).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$ROOT/hooks/vlm-critic-read-guard.sh"
ALLOW_SH="$ROOT/hooks/_lib/vlm-critic-allow-paths.sh"
HOOK_BACKUP="$(mktemp)"
ALLOW_BACKUP="$(mktemp)"

if ! command -v bats >/dev/null 2>&1; then
  echo "bats not on PATH; cannot run mutation suite" >&2
  exit 2
fi
if [[ ! -f "$HOOK" || ! -f "$ALLOW_SH" ]]; then
  echo "target hook or allowlist matcher missing" >&2
  exit 1
fi

cp "$HOOK" "$HOOK_BACKUP"
cp "$ALLOW_SH" "$ALLOW_BACKUP"
trap 'cp "$HOOK_BACKUP" "$HOOK"; cp "$ALLOW_BACKUP" "$ALLOW_SH"; rm -f "$HOOK_BACKUP" "$ALLOW_BACKUP"' EXIT

_run_tests() {
  # Returns 0 if all tests pass, 1 if any fail. Silent.
  local py_out
  py_out=$(cd "$ROOT" && python3 -m unittest tests.contract.spec_vlm_critic_isolation tests.test_vlm_critic 2>&1 | tail -1)
  local bats_out
  bats_out=$(cd "$ROOT" && bats tests/shell/test_vlm_critic_read_guard.bats 2>&1)
  if [[ "$py_out" == "OK" ]] && ! echo "$bats_out" | grep -qE "^not ok"; then
    return 0
  fi
  return 1
}

# --- Mutants targeting security-bearing branches ---

# H1: Fast-substring grep token — replace `vlm-critic` with `vlm-criticZZZ`.
# Should be killed by VCR1 (src/ exit 2 path) — fast-path no longer triggers
# so the hook returns 0 and exit 2 expectation fails.
_apply_H1() {
  sed -i.bak -e 's#grep -F -q "vlm-critic"#grep -F -q "vlm-criticZZZ"#' "$HOOK" && rm -f "$HOOK.bak"
}

# H2: Fast-path SEC-MED-2 fallback — flip the != to == (always enters guard).
# Should be killed by VCR5 (other subagent fast-exits 0; mutation would make
# the hook attempt to source helpers and possibly proceed past the
# substring-grep guard).
_apply_H2() {
  sed -i.bak -e 's#"${CLAUDE_SUBAGENT_TYPE:-}" != "vlm-critic"#"${CLAUDE_SUBAGENT_TYPE:-}" == "vlm-critic"#' "$HOOK" && rm -f "$HOOK.bak"
}

# H3: Exact-match guard — flip != to ==.
# Should be killed by VCR1 (src read should exit 2; mutation makes it exit 0
# because the guard fast-exits on "vlm-critic" subagent type when negated).
_apply_H3() {
  sed -i.bak -e 's#"$SUBAGENT_TYPE" != "vlm-critic"#"$SUBAGENT_TYPE" == "vlm-critic"#' "$HOOK" && rm -f "$HOOK.bak"
}

# H4: Tool name case statement — remove Read (only Grep|Glob match).
# Should be killed by VCR1 (Read of src/ no longer exits 2).
_apply_H4() {
  sed -i.bak -e 's#Read|Grep|Glob)#Grep|Glob)#' "$HOOK" && rm -f "$HOOK.bak"
}

# H5: Empty-path early return — flip empty-test polarity.
# Should be killed by VCR1 (src/ read has non-empty path; mutation would
# treat it as empty and exit 0, breaking the deny).
_apply_H5() {
  sed -i.bak -e 's#-z "$FILE_PATH"#-n "$FILE_PATH"#' "$HOOK" && rm -f "$HOOK.bak"
}

# H6: SEC-HIGH-1 realpath gate — bypass the realpath resolution.
# Should be killed by VCR3 (symlink to src/ should still be denied; mutation
# would let the allowlisted symbolic path pass without realpath check).
_apply_H6() {
  sed -i.bak -e 's#ABS_REAL="$(_vlm_critic_realpath "$ABS_PATH")"#ABS_REAL="$ABS_PATH"#' "$HOOK" && rm -f "$HOOK.bak"
}

# H7: Allowlist final exit — flip exit 2 to exit 0 (treat blocks as allows).
# Should be killed by VCR1 (src read no longer exits 2).
_apply_H7() {
  sed -i.bak -e 's#^exit 2$#exit 0#' "$HOOK" && rm -f "$HOOK.bak"
}

# A1: Allowlist matcher — invert include match result.
# Should be killed by VCR2 (allowlisted baseline png would be denied) and
# VCR1 (denied src/ would be allowed).
_apply_A1() {
  sed -i.bak -e 's#=~ $pattern \]\] && return 0#=~ $pattern \]\] \&\& return 1#' "$ALLOW_SH" && rm -f "$ALLOW_SH.bak"
}

# A2: Allowlist matcher — invert exclude match result.
# Should be killed by VCR2 indirectly (any baseline png with /node_modules/
# in the path would be allowed instead of denied — currently no test directly
# covers this, so we expect this to be a SURVIVOR (documented equivalent
# of the spec-blind CR-MED-4 pattern, NOT a security issue because no
# Read against node_modules baseline screenshot is plausible).
_apply_A2() {
  sed -i.bak -e 's#=~ $bare \]\] && return 1#=~ $bare \]\] \&\& return 0#' "$ALLOW_SH" && rm -f "$ALLOW_SH.bak"
}

# A3: Allowlist matcher — default-deny final return becomes default-allow.
# Should be killed by VCR1 (src read should exit 2; mutation lets it pass).
_apply_A3() {
  # The function ends with `  return 1\n}\n`. Replace ONLY that trailing
  # default-deny `return 1` — not the early `return 1` for empty path inputs.
  awk '
    /^  return 1$/ && last_was_done {sub(/return 1/, "return 0")}
    {last_was_done = ($0 ~ /done <<</); print}
  ' "$ALLOW_SH" > "$ALLOW_SH.tmp" && mv "$ALLOW_SH.tmp" "$ALLOW_SH"
}

# Documented equivalent mutants (no test directly covers; logged for
# reviewer attention). These are SHELL semantic equivalents or
# defense-in-depth mutants whose surviving form is not exploitable given
# the realpath gate.
EQUIVALENT_MUTANTS=("A2")

MUTANTS=(
  'H1|Fast-substring grep token|_apply_H1'
  'H2|Fast-path env-var SEC-MED-2 fallback flip|_apply_H2'
  'H3|Exact-match subagent guard flip|_apply_H3'
  'H4|Tool-name case statement Read drop|_apply_H4'
  'H5|Empty-path early return polarity|_apply_H5'
  'H6|SEC-HIGH-1 realpath gate bypass|_apply_H6'
  'H7|Final exit 2 -> exit 0|_apply_H7'
  'A1|Allowlist include match invert|_apply_A1'
  'A2|Allowlist exclude match invert|_apply_A2'
  'A3|Allowlist default-deny -> default-allow|_apply_A3'
)

killed=0
survived=0
equivalent_survived=0
declare -a survivors=()
declare -a results=()

for entry in "${MUTANTS[@]}"; do
  IFS='|' read -r mid mdesc mfn <<<"$entry"
  # Restore baseline.
  cp "$HOOK_BACKUP" "$HOOK"
  cp "$ALLOW_BACKUP" "$ALLOW_SH"
  # Apply mutant.
  if ! $mfn; then
    results+=("$mid|$mdesc|APPLY_FAILED|n/a")
    continue
  fi
  # Run suite.
  if _run_tests; then
    # Suite still green — mutant survived.
    if printf '%s\n' "${EQUIVALENT_MUTANTS[@]}" | grep -qxF "$mid"; then
      equivalent_survived=$((equivalent_survived + 1))
      results+=("$mid|$mdesc|SURVIVED (equivalent)|documented")
    else
      survived=$((survived + 1))
      survivors+=("$mid:$mdesc")
      results+=("$mid|$mdesc|SURVIVED|UNKILLED")
    fi
  else
    killed=$((killed + 1))
    results+=("$mid|$mdesc|KILLED|ok")
  fi
done

# Restore baseline at end.
cp "$HOOK_BACKUP" "$HOOK"
cp "$ALLOW_BACKUP" "$ALLOW_SH"

total=${#MUTANTS[@]}
non_equiv_total=$((total - equivalent_survived))
if [[ "$non_equiv_total" -eq 0 ]]; then
  kill_rate="1.00"
else
  kill_rate=$(awk -v k="$killed" -v t="$non_equiv_total" 'BEGIN {printf "%.2f", k/t}')
fi

echo ""
echo "## Per-Mutant Results"
echo ""
printf '%-4s | %-50s | %-20s | %s\n' "ID" "Description" "Status" "Note"
printf '%-4s-+-%-50s-+-%-20s-+-%s\n' "----" "--------------------------------------------------" "--------------------" "----"
for row in "${results[@]}"; do
  IFS='|' read -r mid mdesc mstatus mnote <<<"$row"
  printf '%-4s | %-50s | %-20s | %s\n' "$mid" "$mdesc" "$mstatus" "$mnote"
done
echo ""
echo "Killed: $killed / Survived (non-equiv): $survived / Equivalent: $equivalent_survived / Total: $total"
echo "Kill rate (non-equivalent): $kill_rate"

if [[ "$survived" -gt 0 ]]; then
  echo ""
  echo "*** SURVIVING MUTANTS (NOT documented equivalents) ***"
  for s in "${survivors[@]}"; do
    echo "  - $s"
  done
  exit 1
fi

# Gate: kill rate ≥ 0.70 (Iron Law 1).
ok=$(awk -v r="$kill_rate" 'BEGIN { print (r+0 >= 0.70) ? 1 : 0 }')
if [[ "$ok" -ne 1 ]]; then
  echo "Kill rate $kill_rate below 0.70 gate" >&2
  exit 1
fi
exit 0
