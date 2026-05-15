#!/usr/bin/env bash
# Pins the mechanical gate the Slice A AC depends on: `git apply --check`
# rejects a unified-diff hunk whose context anchor doesn't exist in the source
# (the lazy-stub failure mode where an agent uses `...` as a stand-in for
# elided content with a fabricated anchor line).
set -uo pipefail

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git -C "$TMP" init -q
printf 'line1\nline2\nline3\n' > "$TMP/file.txt"
git -C "$TMP" add file.txt
git -C "$TMP" -c user.email=t@t -c user.name=t commit -q -m init

# Patch with a fabricated anchor line ("fictional_anchor_line") that doesn't
# exist in file.txt — this is the lazy-stub shape `git apply --check` must reject.
BAD_PATCH=$(cat <<'EOF'
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 fictional_anchor_line
-line2
+...
 line3
EOF
)

NAME="udiff_git_apply_check_rejects_fabricated_anchor"

if echo "$BAD_PATCH" | git -C "$TMP" apply --check - 2>/dev/null; then
  echo "FAIL: $NAME: git apply --check should reject the malformed patch with fictional anchor"
  exit 1
fi

echo "PASS: $NAME"
exit 0
