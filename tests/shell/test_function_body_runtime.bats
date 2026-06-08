#!/usr/bin/env bats
# Behavioral runtime tests for hooks/function-body-check.sh
# Verifies the default cap (8) and CLAUDE_FUNCTION_LINE_LIMIT override.

setup() {
    # Point the hook's _lib resolution at the repo so log.sh/hook-profile.sh/
    # loop-guard.sh source cleanly on a bare CI runner (no $HOME/.claude tree).
    CLAUDE_PLUGIN_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    export CLAUDE_PLUGIN_ROOT
    HOOK="${CLAUDE_PLUGIN_ROOT}/hooks/function-body-check.sh"
    TMPDIR_FIX="$(mktemp -d "${TMPDIR:-/tmp}/fbcheck.XXXXXX")"
    FIXTURE="${TMPDIR_FIX}/sample.py"
}

teardown() {
    rm -rf "$TMPDIR_FIX"
}

write_py_func() {
    local body_lines="$1"
    local out="$2"
    {
        echo "def my_function():"
        for ((i=1; i<=body_lines; i++)); do
            echo "    x = $i"
        done
    } > "$out"
}

@test "9-line function body warns at default cap (8)" {
    write_py_func 9 "$FIXTURE"
    json="$(printf '{"tool_input":{"file_path":"%s"}}' "$FIXTURE")"
    run bash -c "echo '$json' | bash '$HOOK' 2>&1 1>/dev/null"
    [[ "$output" == *"exceeds"* ]]
}

@test "9-line function body does NOT warn when CLAUDE_FUNCTION_LINE_LIMIT=20" {
    write_py_func 9 "$FIXTURE"
    json="$(printf '{"tool_input":{"file_path":"%s"}}' "$FIXTURE")"
    run bash -c "echo '$json' | CLAUDE_FUNCTION_LINE_LIMIT=20 bash '$HOOK' 2>&1 1>/dev/null"
    [[ "$output" != *"exceeds"* ]]
}

@test "5-line function body does NOT warn at default cap (8)" {
    write_py_func 5 "$FIXTURE"
    json="$(printf '{"tool_input":{"file_path":"%s"}}' "$FIXTURE")"
    run bash -c "echo '$json' | bash '$HOOK' 2>&1 1>/dev/null"
    [[ "$output" != *"exceeds"* ]]
}
