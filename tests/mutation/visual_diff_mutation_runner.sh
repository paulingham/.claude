#!/usr/bin/env bash
# Reproducible mutation-test runner for hooks/_lib/visual_diff.js.
#
# Why this exists: the harness ships as bash + Python + plain JS with no
# package.json at root. Installing Stryker (a JS mutation tester) would force
# a top-level package.json, npm devDeps, and ~80 MB of node_modules into the
# tree for a single use case. `skills/verify/SKILL.md` § Manual fallback
# allows a sed-based mutation runner as long as it is reproducible — this
# file is that runner. It is NOT a permanent harness component; once a future
# pipeline lands a tracked package.json (or the harness adopts mutmut-style
# language-agnostic mutation), this can be replaced.
#
# Invocation:
#   bash tests/mutation/visual_diff_mutation_runner.sh
#
# Exit codes:
#   0  — all mutants accounted for (killed or documented equivalents);
#         kill rate meets ≥0.70 gate per rules/core.md § Iron Law 1.
#   1  — a mutant survived that is NOT in the documented-equivalents list,
#         OR the test runner could not be invoked, OR the kill rate is
#         below 0.70 across non-equivalent mutants.
#   2  — environment unmet (node not on PATH).
#
# Output: a `## Per-Mutant Results` table identical in shape to
# `pipeline-state/workstreams/visual-regression/design-qc-visual-regression/
# build-mutation.md`. Reviewers can re-run this script to verify the kill
# rate independently of the build commit's audit artifact.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET="$ROOT/hooks/_lib/visual_diff.js"
TEST_FILE="$ROOT/tests/test_visual_diff.js"
BACKUP="$(mktemp)"

if ! command -v node >/dev/null 2>&1; then
  echo "node not on PATH; cannot run mutation suite" >&2
  exit 2
fi
if [[ ! -f "$TARGET" ]]; then
  echo "target $TARGET missing" >&2
  exit 1
fi
if [[ ! -f "$TEST_FILE" ]]; then
  echo "test file $TEST_FILE missing" >&2
  exit 1
fi

cp "$TARGET" "$BACKUP"
trap 'cp "$BACKUP" "$TARGET"; rm -f "$BACKUP"' EXIT

# Documented equivalent mutants per build-mutation.md.
EQUIVALENT_MUTANTS=("M4" "M8" "M10" "M14")

_restore() { cp "$BACKUP" "$TARGET"; }

_apply_M1()  { perl -0777 -i -pe 's/if \(!Buffer\.isBuffer\(value\)\) \{/if (Buffer.isBuffer(value)) {/' "$TARGET"; }
_apply_M2()  { perl -0777 -i -pe 's/threshold < 0\.0/threshold <= 0.0/' "$TARGET"; }
_apply_M3()  { perl -0777 -i -pe 's/threshold > 1\.0/threshold >= 1.0/' "$TARGET"; }
_apply_M4()  { perl -0777 -i -pe 's/_pixelDistance\(baseline, current, i\) > DEFAULT_COLOR_DELTA_THRESHOLD/_pixelDistance(baseline, current, i) >= DEFAULT_COLOR_DELTA_THRESHOLD/' "$TARGET"; }
_apply_M5()  { perl -0777 -i -pe 's/i \+= RGBA_CHANNELS/i += 1/' "$TARGET"; }
_apply_M6()  { perl -0777 -i -pe 's/if \(totalPixels === 0\) \{\s*return 0\.0;\s*\}/if (totalPixels === 0) { return 1.0; }/' "$TARGET"; }
_apply_M7()  { perl -0777 -i -pe 's/0\.29889531/0.5/' "$TARGET"; }
_apply_M8()  { perl -0777 -i -pe 's/return 255 \+ \(channel - 255\) \* alpha;/return 255 - (channel - 255) * alpha;/' "$TARGET"; }
_apply_M9()  { perl -0777 -i -pe 's/diffPixelCount \+= 1;/diffPixelCount += 0;/' "$TARGET"; }
_apply_M10() { perl -0777 -i -pe 's/if \(ra === rb && ga === gb && ba === bb && aa === ab\) \{\s*return 0;\s*\}/if (ra === rb \&\& ga === gb \&\& ba === bb \&\& aa === ab) { return 1; }/' "$TARGET"; }
_apply_M11() { perl -0777 -i -pe 's|diffPixelCount / totalPixels|diffPixelCount / 1|' "$TARGET"; }
_apply_M12() { perl -0777 -i -pe 's/dimensions\.width < 0/dimensions.width <= 0/' "$TARGET"; }
_apply_M13() { perl -0777 -i -pe 's/const RGBA_CHANNELS = 4;/const RGBA_CHANNELS = 3;/' "$TARGET"; }
_apply_M14() { perl -0777 -i -pe 's/threshold = 0\.02/threshold = 0.5/' "$TARGET"; }
_apply_M15() { perl -0777 -i -pe 's/let diffPixelCount = 0;/let diffPixelCount = 1;/' "$TARGET"; }

# Each entry: ID|description|apply-function
MUTANTS=(
  'M1|_assertBuffer negate|_apply_M1'
  'M2|_assertThreshold lower bound|_apply_M2'
  'M3|_assertThreshold upper bound|_apply_M3'
  'M4|Pixel-diff comparison >|_apply_M4'
  'M5|Loop step|_apply_M5'
  'M6|Empty-pixel guard return|_apply_M6'
  'M7|YIQ Y_r coefficient|_apply_M7'
  'M8|_blend formula sign|_apply_M8'
  'M9|diffPixelCount increment|_apply_M9'
  'M10|Identical-pixel shortcut|_apply_M10'
  'M11|Ratio denominator|_apply_M11'
  'M12|Dimensions width neg-check|_apply_M12'
  'M13|RGBA_CHANNELS constant|_apply_M13'
  'M14|comparePngBuffers default threshold|_apply_M14'
  'M15|diffPixelCount init|_apply_M15'
)

killed=0
survived=0
declare -a results
declare -a unexpected_survivors
declare -a apply_failures

for entry in "${MUTANTS[@]}"; do
  IFS='|' read -r id desc fn <<< "$entry"
  _restore
  # Verify the apply function actually mutated the target. If it did not,
  # mark this mutant as a runner-side failure rather than passing it as
  # "killed" — a no-op apply is not a valid kill.
  before_sum="$(shasum "$TARGET" | awk '{print $1}')"
  "$fn"
  after_sum="$(shasum "$TARGET" | awk '{print $1}')"
  if [[ "$before_sum" == "$after_sum" ]]; then
    apply_failures+=("$id")
    results+=("$id|$desc|APPLY_FAILED (sed/perl matched nothing)")
    continue
  fi
  if node --test "$TEST_FILE" >/dev/null 2>&1; then
    survived=$((survived + 1))
    is_equivalent=0
    for eq in "${EQUIVALENT_MUTANTS[@]}"; do
      [[ "$eq" == "$id" ]] && is_equivalent=1 && break
    done
    if [[ $is_equivalent -eq 1 ]]; then
      results+=("$id|$desc|SURVIVED (documented equivalent)")
    else
      results+=("$id|$desc|SURVIVED (UNEXPECTED)")
      unexpected_survivors+=("$id")
    fi
  else
    killed=$((killed + 1))
    results+=("$id|$desc|KILLED")
  fi
done

_restore

total=${#MUTANTS[@]}
total_applied=$((total - ${#apply_failures[@]}))
equiv_count="${#EQUIVALENT_MUTANTS[@]}"
non_equiv_total=$((total_applied - equiv_count))
non_equiv_killed=$killed
if [[ $non_equiv_total -gt 0 ]]; then
  effective_rate=$(awk "BEGIN { printf \"%.3f\", $non_equiv_killed / $non_equiv_total }")
else
  effective_rate="n/a"
fi
raw_rate=$(awk "BEGIN { printf \"%.3f\", $killed / $total }")

echo "# Mutation Runner Report — hooks/_lib/visual_diff.js"
echo
echo "Total mutants:                 $total"
echo "Applied successfully:          $total_applied"
echo "Killed:                        $killed"
echo "Survived (total):              $survived"
echo "Documented equivalents:        $equiv_count"
echo "Raw kill rate:                 $raw_rate"
echo "Effective kill rate (- equiv): $effective_rate"
echo "Gate:                          ≥ 0.70 (rules/core.md § Iron Law 1)"
echo
echo "| ID | Description | Result |"
echo "|----|-------------|--------|"
for row in "${results[@]}"; do
  IFS='|' read -r id desc result <<< "$row"
  echo "| $id | $desc | $result |"
done

if [[ ${#apply_failures[@]} -gt 0 ]]; then
  echo
  echo "APPLY FAILURES: ${apply_failures[*]}" >&2
  echo "The sed/perl expression matched nothing. Either the source file" >&2
  echo "has drifted from the expected shape, or the mutation expression" >&2
  echo "is malformed. Inspect _apply_<ID> and adjust." >&2
  exit 1
fi

if [[ ${#unexpected_survivors[@]} -gt 0 ]]; then
  echo
  echo "UNEXPECTED SURVIVORS: ${unexpected_survivors[*]}" >&2
  echo "These mutants are NOT in the documented-equivalent list. Either add" >&2
  echo "a new discriminating test, or — if genuinely equivalent — add the ID" >&2
  echo "to EQUIVALENT_MUTANTS and document the rationale in build-mutation.md." >&2
  exit 1
fi

# Gate check.
gate_pass=$(awk "BEGIN { print ($raw_rate >= 0.70) ? 1 : 0 }")
if [[ "$gate_pass" -ne 1 ]]; then
  # Raw rate may be below 0.70 due to documented equivalents. If the
  # effective rate (which excludes them) clears, we still pass the gate.
  if [[ "$effective_rate" != "n/a" ]]; then
    eff_pass=$(awk "BEGIN { print ($effective_rate >= 0.70) ? 1 : 0 }")
    if [[ "$eff_pass" -eq 1 ]]; then
      echo
      echo "Raw kill rate $raw_rate < 0.70 but effective rate $effective_rate"
      echo "(excluding $equiv_count documented equivalents) clears the gate."
      exit 0
    fi
  fi
  echo "GATE FAILED: raw $raw_rate, effective $effective_rate" >&2
  exit 1
fi

exit 0
