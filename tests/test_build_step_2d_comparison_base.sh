#!/usr/bin/env bash
# AC6 — Step 2d body documents verbatim
#   git diff --name-only $(git merge-base HEAD main)...HEAD
# and does NOT document the bare form `git diff --name-only HEAD`.
# Scope of search = body of Step 2d (header line .. next `### Step` line).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

# Extract Step 2d body: from "### Step 2d" up to (but not including) next "### Step".
STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

echo "Test step_2d_uses_merge_base_diff"

assert "Step 2d body non-empty" test -n "$STEP_BODY"

# Verbatim merge-base form must appear.
if printf '%s' "$STEP_BODY" | grep -qF 'git diff --name-only $(git merge-base HEAD main)...HEAD'; then
  echo "  ok: merge-base diff form present (verbatim)"; PASS=$((PASS + 1))
else
  echo "  FAIL: merge-base diff form missing"; FAIL=$((FAIL + 1))
fi

# Bare form MUST NOT appear. Use a regex that matches the bare form but NOT the
# merge-base form (the merge-base form contains "...HEAD" not bare "HEAD").
# The bare form: `git diff --name-only HEAD` followed by end-of-line or whitespace,
# never followed by `~` or `...` or `^`.
if printf '%s' "$STEP_BODY" | grep -qE 'git diff --name-only HEAD([[:space:]]|$|`)'; then
  echo "  FAIL: bare 'git diff --name-only HEAD' form present (forbidden)"; FAIL=$((FAIL + 1))
else
  echo "  ok: bare 'git diff --name-only HEAD' form absent"; PASS=$((PASS + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
