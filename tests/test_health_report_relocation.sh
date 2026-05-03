#!/usr/bin/env bash
# Slice C — health-scan output relocation policy test.
#
# Per plan § Group 7 (POLICY) + R12: health reports relocate from
# `pipeline-state/health-report-{date}.md` (flat, task-namespace overlap)
# to `pipeline-state/health-reports/{date}.md` (subdir, unscoped — health
# is project-wide). Existing on-disk reports are NOT migrated by Slice F.
#
# Test contract: the SKILL.md text documents the new path AND does NOT
# reference the legacy `health-report-{date}.md` flat write-path.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="$REPO_ROOT/skills/health-scan/SKILL.md"

PASS=0
FAIL=0

assert_present() {
  local needle="$1" label="$2"
  if grep -qF "$needle" "$SKILL"; then
    echo "  ok: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (missing '$needle')"
    FAIL=$((FAIL + 1))
  fi
}

assert_absent() {
  local needle="$1" label="$2"
  # Allow the needle to appear inside a "legacy" / "do NOT" / soak comment.
  # The strict check: the needle MUST NOT appear as the documented WRITE path.
  # We assert the LEGACY shape `pipeline-state/health-report-{date}.md` is
  # absent from the file body. If a deprecation note must include it, it
  # should be inside an explicit "Legacy:" or "(deprecated)" line.
  if grep -F "$needle" "$SKILL" | grep -vqE '(Legacy|legacy|deprecated|DEPRECATED|removed)'; then
    echo "  FAIL: $label ('$needle' still appears as a non-legacy reference)"
    FAIL=$((FAIL + 1))
  else
    echo "  ok: $label"
    PASS=$((PASS + 1))
  fi
}

echo "Test: health_scan_writes_under_health_reports_subdir"
assert_present "pipeline-state/health-reports/{date}.md" "new layout documented"
assert_absent  "pipeline-state/health-report-{date}.md"  "legacy flat path removed"

echo "Summary: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
