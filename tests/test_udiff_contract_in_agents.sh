#!/usr/bin/env bash
# Slice A — adopt-udiff-assertflip: byte-pin contract tests for agent .md files.
# Asserts each Build agent prescribes the unified-diff edit format, preserves
# the orchestrator-apply structured payload, and keeps the parent-inheritance
# pointer for frontend-engineer.
set -euo pipefail

CLAUDE_HOME="${CLAUDE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

PASS=0; FAIL=0

report_pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
report_fail() { echo "FAIL: $1 — $2" >&2; FAIL=$((FAIL + 1)); }

grep_file() {
  local label=$1 file=$2 needle=$3
  if grep -qF -- "$needle" "$file"; then
    report_pass "$label"
  else
    report_fail "$label" "expected literal '$needle' in $file"
  fi
}

SE="$CLAUDE_HOME/agents/software-engineer.md"
FE="$CLAUDE_HOME/agents/fix-engineer.md"
FRONT="$CLAUDE_HOME/agents/frontend-engineer.md"

# test_software_engineer_prescribes_udiff
grep_file "test_software_engineer_prescribes_udiff" "$SE" 'unified diff applicable via `git apply`'

# test_fix_engineer_prescribes_udiff
grep_file "test_fix_engineer_prescribes_udiff" "$FE" 'unified diff applicable via `git apply`'

# test_frontend_engineer_inherits_udiff (regression guard on parent pointer)
grep_file "test_frontend_engineer_inherits_udiff" "$FRONT" 'parent: software-engineer'

# test_fix_engineer_preserves_orchestrator_apply_payload — all three literals
for literal in 'file_path' 'old_string' 'new_string'; do
  grep_file "test_fix_engineer_preserves_orchestrator_apply_payload[$literal]" "$FE" "$literal"
done

# test_write_reserved_for_new_files
grep_file "test_write_reserved_for_new_files" "$SE" 'Write tool reserved for net-new files'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
