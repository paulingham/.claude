#!/usr/bin/env bash
# Validates Story 1 case format schema + directory scaffolding.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
EX="$ROOT/eval/cases/_example"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/checks.sh"

check_artifacts "$EX"
check_metadata "$EX/metadata.json"
check_gitignore "$ROOT"
check_docs "$ROOT" "$EX"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
