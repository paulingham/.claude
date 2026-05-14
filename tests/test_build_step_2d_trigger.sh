#!/usr/bin/env bash
# AC7 — Step 2d body lists all five path-glob trigger tokens:
#   app/**, src/**, pages/**, components/**, **/*.{tsx,jsx,vue,svelte,html,css}
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

GLOBS=(
  'app/**'
  'src/**'
  'pages/**'
  'components/**'
  '**/*.{tsx,jsx,vue,svelte,html,css}'
)

echo "Test step_2d_documents_path_glob"

for glob in "${GLOBS[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$glob"; then
    echo "  ok: glob token present: $glob"; PASS=$((PASS + 1))
  else
    echo "  FAIL: glob token missing: $glob"; FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
