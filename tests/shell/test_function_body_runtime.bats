#!/usr/bin/env bats
# Slice B — behavioral runtime tests for hooks/function-body-check.sh.
# Per-language smell limits (Ruby 5 / TS 12; py/go fallback 8) PLUS block-on-new:
# a new/changed over-limit function blocks (exit 2); a legacy over-limit function
# is advisory (exit 0). New/legacy is discriminated against a real git baseline,
# so every block-on-new fixture lives INSIDE a committed temp git repo — without
# that, the hook's git calls fail and it fails open to advisory, turning a
# block-test into a false green. Precedent: tests/shell/codebase_map_hooks.bats.

setup() {
    CLAUDE_PLUGIN_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    export CLAUDE_PLUGIN_ROOT
    HOOK="${CLAUDE_PLUGIN_ROOT}/hooks/function-body-check.sh"

    # Real temp git repo: fixtures committed here become the "legacy" baseline;
    # files added after the commit are "new". The hook resolves REPO_ROOT from
    # the file's directory, so the fixtures must live under this repo.
    REPO_FIX="$(mktemp -d "${TMPDIR:-/tmp}/fbcheck.XXXXXX")"
    # Hermetic loop-guard state per test: each AC invokes the hook several times;
    # a shared counter would trip the re-entrancy guard (>10 calls/60s) and make
    # the hook fast-exit 0, masking the real block/advisory verdict. Isolating
    # CLAUDE_STATE_DIR per test keeps the guard counter fresh.
    CLAUDE_STATE_DIR="${REPO_FIX}/.state"
    export CLAUDE_STATE_DIR
    git -C "$REPO_FIX" init -q
    git -C "$REPO_FIX" config user.email t@t
    git -C "$REPO_FIX" config user.name t
    printf 'placeholder = 1\n' > "$REPO_FIX/base.txt"
    git -C "$REPO_FIX" add base.txt
    git -C "$REPO_FIX" commit -q -m base
}

teardown() {
    rm -rf "$REPO_FIX"
}

run_hook() {
    local file="$1"
    local json
    json="$(printf '{"tool_input":{"file_path":"%s"}}' "$file")"
    run bash -c "echo '$json' | bash '$HOOK' 2>&1"
}

write_rb_func() {
    local body_lines="$1" out="$2" i
    {
        echo "def my_method"
        for ((i = 1; i <= body_lines; i++)); do echo "  x = $i"; done
        echo "end"
    } > "$out"
}

write_ts_func() {
    local body_lines="$1" out="$2" i
    {
        echo "function myFunction() {"
        for ((i = 1; i <= body_lines; i++)); do echo "  const x$i = $i;"; done
        echo "}"
    } > "$out"
}

@test "B4: new 6-line Ruby function blocks (exit 2) against Ruby limit 5" {
    write_rb_func 6 "$REPO_FIX/new.rb"
    run_hook "$REPO_FIX/new.rb"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "B5: new 13-line TS function blocks (exit 2) against TS limit 12" {
    write_ts_func 13 "$REPO_FIX/new.ts"
    run_hook "$REPO_FIX/new.ts"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "B6: new 9-line TS function passes (exit 0), no BLOCK, under TS limit 12" {
    write_ts_func 9 "$REPO_FIX/ok.ts"
    run_hook "$REPO_FIX/ok.ts"
    [ "$status" -eq 0 ]
    [[ "$output" != *"BLOCKED"* ]]
}

@test "B7: pre-existing over-limit Ruby function with unrelated edit is advisory (exit 0)" {
    # Commit an over-limit Ruby function to the baseline; the offending function
    # is legacy. Then append a small (under-limit) function below it. The diff
    # hunk touches only the tail, so the legacy violator's def line falls outside
    # the changed range and must NOT block.
    local f="$REPO_FIX/legacy.rb"
    write_rb_func 8 "$f"
    git -C "$REPO_FIX" add legacy.rb
    git -C "$REPO_FIX" commit -q -m legacy
    {
        echo ""
        echo "def small"
        echo "  1"
        echo "end"
    } >> "$f"
    run_hook "$f"
    [ "$status" -eq 0 ]
    [[ "$output" != *"BLOCKED"* ]]

    # Anti-false-green guard: the advisory above must be a real legacy decision,
    # NOT the hook failing open on a broken git baseline. Append a NEW over-limit
    # function to the SAME tracked file in the SAME repo — its def line lands in
    # the changed hunk, so it MUST block. If the repo/git wiring were broken this
    # would also (wrongly) pass advisory, exposing the false green.
    {
        echo ""
        echo "def freshly_added"
        echo "  a = 1"
        echo "  b = 2"
        echo "  c = 3"
        echo "  d = 4"
        echo "  e = 5"
        echo "  f = 6"
        echo "end"
    } >> "$f"
    run_hook "$f"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "B8: CLAUDE_FUNCTION_LINE_LIMIT override raises the effective cap (back-compat)" {
    # A new 9-line .py function blocks at the default 8, but passes when the
    # override lifts the cap to 20 — proving the env override still tunes the cap.
    local f="$REPO_FIX/sample.py"
    {
        echo "def my_function():"
        local i
        for ((i = 1; i <= 9; i++)); do echo "    x = $i"; done
    } > "$f"
    local json
    json="$(printf '{"tool_input":{"file_path":"%s"}}' "$f")"
    run bash -c "echo '$json' | CLAUDE_FUNCTION_LINE_LIMIT=20 bash '$HOOK' 2>&1"
    [ "$status" -eq 0 ]
    [[ "$output" != *"BLOCKED"* ]]
}

@test "B9: brand-new untracked file with over-limit function blocks (ls-files discriminator)" {
    # The file is created but never git-added: ls-files --error-unmatch fails,
    # so ALL violations are treated as new and block.
    write_rb_func 6 "$REPO_FIX/untracked.rb"
    run_hook "$REPO_FIX/untracked.rb"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}
