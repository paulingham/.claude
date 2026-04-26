#!/usr/bin/env bash
# Integration test for /tool-synthesis register + run + cleanup + isolation.
# Verifies:
#   1. register.sh creates .claude-scratch-tools/ if missing
#   2. register.sh writes a per-worktree registry entry
#   3. registered tool is executable and runnable
#   4. registry isolates per-worktree (no cross-leak)
#   5. cleanup.sh removes the scratch directory entirely
#   6. .gitignore prevents the directory from being committed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="${SCRIPT_DIR}/../lib"

WORKTREE_A="$(mktemp -d)"
WORKTREE_B="$(mktemp -d)"
trap 'rm -rf "$WORKTREE_A" "$WORKTREE_B"' EXIT

assert_eq() {
  local expected="$1" actual="$2" label="$3"
  if [ "$expected" = "$actual" ]; then
    echo "PASS: ${label}"
  else
    echo "FAIL: ${label} (expected='${expected}' actual='${actual}')" >&2
    exit 1
  fi
}

assert_file_exists() {
  if [ -e "$1" ]; then
    echo "PASS: $2"
  else
    echo "FAIL: $2 (missing $1)" >&2
    exit 1
  fi
}

assert_file_absent() {
  if [ ! -e "$1" ]; then
    echo "PASS: $2"
  else
    echo "FAIL: $2 (unexpected $1)" >&2
    exit 1
  fi
}

setup_repo() {
  local dir="$1"
  cd "$dir"
  git init -q
  git config user.email tool-synth@test.local
  git config user.name tool-synth
  git config commit.gpgsign false
  git config tag.gpgsign false
  echo "src" > main.txt
  git add main.txt
  git -c commit.gpgsign=false commit -q -m "init"
}

# --- Test 1: register creates dir + registry, marks tool executable ---
setup_repo "$WORKTREE_A"
cd "$WORKTREE_A"

cat > /tmp/grep_imports.sh <<'EOF'
#!/usr/bin/env bash
echo "imports of $1: 0"
EOF

"$LIB/register.sh" grep-imports /tmp/grep_imports.sh "Find all imports of a symbol" >/dev/null

assert_file_exists "$WORKTREE_A/.claude-scratch-tools/grep-imports" "tool copied into scratch dir"
assert_file_exists "$WORKTREE_A/.claude-scratch-tools/registry.json" "registry created"
assert_file_exists "$WORKTREE_A/.claude-scratch-tools/.gitignore" "scratch-dir self-gitignore created"

if [ ! -x "$WORKTREE_A/.claude-scratch-tools/grep-imports" ]; then
  echo "FAIL: tool not executable" >&2
  exit 1
fi
echo "PASS: tool marked executable"

# --- Test 2: registry contains tool name + description ---
grep -q '"name": "grep-imports"' "$WORKTREE_A/.claude-scratch-tools/registry.json" \
  && echo "PASS: registry has tool name" \
  || { echo "FAIL: registry missing name" >&2; exit 1; }

grep -q "Find all imports of a symbol" "$WORKTREE_A/.claude-scratch-tools/registry.json" \
  && echo "PASS: registry has description" \
  || { echo "FAIL: registry missing description" >&2; exit 1; }

# --- Test 3: registered tool runs ---
output="$("$WORKTREE_A/.claude-scratch-tools/grep-imports" foo)"
assert_eq "imports of foo: 0" "$output" "synthesised tool runs"

# --- Test 4: per-worktree isolation (registering in B does not touch A) ---
setup_repo "$WORKTREE_B"
cd "$WORKTREE_B"
cat > /tmp/ast_count.sh <<'EOF'
#!/usr/bin/env bash
echo "ast nodes: 42"
EOF
"$LIB/register.sh" ast-count /tmp/ast_count.sh "Count AST nodes" >/dev/null

assert_file_exists "$WORKTREE_B/.claude-scratch-tools/ast-count" "tool registered in B"
assert_file_absent "$WORKTREE_A/.claude-scratch-tools/ast-count" "tool NOT in A (isolation)"
assert_file_absent "$WORKTREE_B/.claude-scratch-tools/grep-imports" "A tool NOT in B (isolation)"

# --- Test 5: list shows registered tools ---
listing="$("$LIB/register.sh" --list "$WORKTREE_A" 2>&1)"
echo "$listing" | grep -q "grep-imports" \
  && echo "PASS: --list shows registered tools" \
  || { echo "FAIL: --list missing tool" >&2; exit 1; }

# --- Test 6: cleanup removes the directory entirely ---
"$LIB/register.sh" --cleanup "$WORKTREE_A" >/dev/null
assert_file_absent "$WORKTREE_A/.claude-scratch-tools" "cleanup removes scratch dir"

# --- Test 7: scratch dir would be ignored by git (gitignore at repo root) ---
cd "$WORKTREE_B"
echo ".claude-scratch-tools/" > .gitignore
git add .gitignore
git -c commit.gpgsign=false commit -q -m "gitignore"

# Re-create a tool in B (cleanup didn't run for B)
ignored_check="$(git status --porcelain --ignored | grep '.claude-scratch-tools' | head -1 || true)"
case "$ignored_check" in
  "!! .claude-scratch-tools/"*) echo "PASS: scratch dir is gitignored at repo root" ;;
  *) echo "FAIL: scratch dir NOT gitignored (got: '$ignored_check')" >&2; exit 1 ;;
esac

# --- Test 8: re-register is idempotent (no duplicate registry entries) ---
cd "$WORKTREE_B"
"$LIB/register.sh" ast-count /tmp/ast_count.sh "Count AST nodes" >/dev/null
count="$(grep -c '"name": "ast-count"' "$WORKTREE_B/.claude-scratch-tools/registry.json")"
assert_eq "1" "$count" "re-register is idempotent"

# --- Test 9: refuses tool name with shell-unsafe chars ---
if "$LIB/register.sh" "bad;name" /tmp/ast_count.sh "x" 2>/dev/null; then
  echo "FAIL: accepted unsafe tool name" >&2
  exit 1
fi
echo "PASS: refuses unsafe tool name"

# --- Test 10: harness root .gitignore excludes .claude-scratch-tools ---
HARNESS_GITIGNORE="${SCRIPT_DIR}/../../../.gitignore"
if grep -q "claude-scratch-tools" "$HARNESS_GITIGNORE"; then
  echo "PASS: harness .gitignore excludes scratch dir"
else
  echo "FAIL: harness .gitignore missing scratch-dir exclusion" >&2
  exit 1
fi

echo ""
echo "ALL TESTS PASSED"
