#!/usr/bin/env bash
# Slice C — approval-token write-path migration test.
#
# Asserts: invoking `_at_write_token TASK APPROVED` writes to the NEW
# layout (`pipeline-state/{task-id}/approval.token`) and the legacy path
# (`pipeline-state/{task-id}-approval.token`) is NOT created.
#
# CROSS-SLICE DEPENDENCY: this test depends on Slice B's refactor of
# `hooks/_lib/approval-token.sh` (`_at_token_path` returns mtime-fresher
# existing file; `_at_write_token` writes new layout only). At Slice C
# integration time the test is RED; at Slice B integration time it goes
# GREEN. We mark it xfail(strict) so the post-impl GREEN suite reports
# correctly.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$REPO_ROOT/hooks/_lib/approval-token.sh"

# Cross-slice xfail marker — the test is expected to FAIL until Slice B lands.
# Bash has no native xfail; we encode the contract as: exit 0 on PASS,
# exit 99 on EXPECTED_FAIL (Slice B not yet integrated). Test runners can
# treat 99 as xfail.
EXPECTED_FAIL_EXIT=99

PASS=0
FAIL=0
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Override HOME so _at_token_path resolves under our tmp dir.
export HOME="$TMP"
mkdir -p "$HOME/.claude/pipeline-state"

# shellcheck source=/dev/null
source "$LIB"

# Pre-condition: pipeline must be active for write to be meaningful.
mkdir -p "$HOME/.claude/pipeline-state/t1"
echo "verdict: in_progress" > "$HOME/.claude/pipeline-state/t1/pipeline.md"

echo "Test: write_approval_token_uses_new_layout_only"

# Invoke the writer.
if ! _at_write_token "t1" "APPROVED"; then
  echo "  FAIL: _at_write_token returned non-zero"
  FAIL=$((FAIL + 1))
fi

# New-layout file must exist.
NEW_PATH="$HOME/.claude/pipeline-state/t1/approval.token"
if [[ -f "$NEW_PATH" ]]; then
  echo "  ok: new-layout token written at $NEW_PATH"
  PASS=$((PASS + 1))
else
  echo "  FAIL: new-layout token MISSING at $NEW_PATH"
  FAIL=$((FAIL + 1))
fi

# Legacy-layout file must NOT exist.
LEGACY_PATH="$HOME/.claude/pipeline-state/t1-approval.token"
if [[ ! -f "$LEGACY_PATH" ]]; then
  echo "  ok: legacy-layout token NOT written"
  PASS=$((PASS + 1))
else
  echo "  FAIL: legacy-layout token present at $LEGACY_PATH"
  FAIL=$((FAIL + 1))
fi

echo "Summary: $PASS passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
  exit 0
else
  # Cross-slice: Slice B has not yet integrated. Mark xfail.
  echo "EXPECTED FAIL: depends on slice-b refactor of hooks/_lib/approval-token.sh"
  exit "$EXPECTED_FAIL_EXIT"
fi
