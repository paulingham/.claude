#!/usr/bin/env bash
# TDD Guard — PreToolUse hook on Write and Edit
# Blocks implementation edits on existing source files when no test file exists.
# Enforces RED-first TDD at the infrastructure level.

set -euo pipefail

# Require jq — exit cleanly if not available (don't silently bypass)
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)

# Never block if stop_hook_active (avoid loops)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Extract the file path (Write uses file_path, Edit uses path)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Reject paths with newlines or control characters (safety against malformed JSON input)
if [[ "$FILE_PATH" == *$'\n'* ]] || [[ "$FILE_PATH" == *$'\r'* ]]; then
  exit 0
fi

# Only check source file extensions
case "$FILE_PATH" in
  *.rb|*.js|*.ts|*.jsx|*.tsx|*.py|*.go|*.java|*.cs|*.swift|*.kt) ;;
  *) exit 0 ;;
esac

# Skip if this IS a test file
case "$FILE_PATH" in
  *spec/*|*test/*|*__tests__/*|*.test.*|*.spec.*|*_test.go|*_test.py) exit 0 ;;
esac

# Skip config and lock files
case "$FILE_PATH" in
  *package.json|*Gemfile|*.toml|*.yaml|*.yml|*.json|*.sh|*.md|*.lock) exit 0 ;;
esac

# Skip if file doesn't exist yet — agent may be writing the test first
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Determine expected test file location based on language
TEST_FOUND=false

case "$FILE_PATH" in
  *.rb)
    # Ruby: lib/foo.rb → spec/lib/foo_spec.rb or spec/foo_spec.rb
    BASENAME=$(basename "$FILE_PATH" .rb)
    DIRPART=$(dirname "$FILE_PATH")
    SPEC_MIRROR="${DIRPART/\/lib\//\/spec\/lib\/}/${BASENAME}_spec.rb"
    SPEC_ROOT="spec/${BASENAME}_spec.rb"
    [ -f "$SPEC_MIRROR" ] || [ -f "$SPEC_ROOT" ] && TEST_FOUND=true
    EXPECTED="$SPEC_MIRROR"
    ;;
  *.py)
    # Python: src/foo.py → tests/test_foo.py or test_foo.py
    BASENAME=$(basename "$FILE_PATH" .py)
    [ -f "tests/test_${BASENAME}.py" ] || [ -f "test_${BASENAME}.py" ] && TEST_FOUND=true
    EXPECTED="tests/test_${BASENAME}.py"
    ;;
  *.js|*.ts|*.jsx|*.tsx)
    # JS/TS: src/foo.ts → src/foo.test.ts or src/__tests__/foo.test.ts or __tests__/foo.test.ts
    BASENAME=$(basename "$FILE_PATH")
    EXT="${BASENAME##*.}"
    BASE="${BASENAME%.*}"
    DIRPART=$(dirname "$FILE_PATH")
    [ -f "${DIRPART}/${BASE}.test.${EXT}" ] || \
    [ -f "${DIRPART}/${BASE}.spec.${EXT}" ] || \
    [ -f "${DIRPART}/__tests__/${BASE}.test.${EXT}" ] || \
    [ -f "__tests__/${BASE}.test.${EXT}" ] && TEST_FOUND=true
    EXPECTED="${DIRPART}/${BASE}.test.${EXT}"
    ;;
  *.go)
    # Go: foo.go → foo_test.go (in same directory)
    GOTEST="${FILE_PATH%.go}_test.go"
    [ -f "$GOTEST" ] && TEST_FOUND=true
    EXPECTED="$GOTEST"
    ;;
  *.java)
    BASENAME=$(basename "$FILE_PATH" .java)
    if [[ ! "$BASENAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
      exit 0
    fi
    find . -maxdepth 6 -name "${BASENAME}Test.java" -o -name "Test${BASENAME}.java" 2>/dev/null | grep -q . && TEST_FOUND=true
    EXPECTED="src/test/java/.../${BASENAME}Test.java"
    ;;
  *.swift|*.kt|*.cs)
    # Conservative: allow these through (test conventions vary widely)
    exit 0
    ;;
esac

if [ "$TEST_FOUND" = "true" ]; then
  exit 0
fi

# Block: no test file found
jq -n --arg path "$FILE_PATH" --arg expected "$EXPECTED" \
  '{"decision":"block","reason":("TDD Guard: No test file found for \u0027" + $path + "\u0027. Write the test first (RED phase). Expected: " + $expected)}'
exit 1
