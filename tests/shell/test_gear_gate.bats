#!/usr/bin/env bats
# Phase B WS2 — hooks/_lib/gear-gate.sh unit tests.
# check_gear_gate <sid>: return 1 (skip) ONLY on a successfully-read PAIR
# gear, keyed by SESSION ID (not PPID) — gear-select.sh (a UserPromptSubmit
# hook) and the gear-gated hooks (PreToolUse/SubagentStop/CLI-invoked) are
# DIFFERENT subprocesses with different PPIDs, so PPID-keying can never
# round-trip across them. Session id is the one value stable across the
# whole session (see hooks/_lib/session-id.sh). Fail-safe: any sid that
# resolves to no gear marker (or an unreadable state dir) -> RUN the hook.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP="$(mktemp -d -t gear-gate.XXXXXX)"
  export CLAUDE_STATE_DIR="$TMP/state"
  export CLAUDE_PLUGIN_DATA="$TMP/harness-data"
  mkdir -p "$CLAUDE_STATE_DIR"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/hooks/_lib/gear-gate.sh"
}

teardown() {
  rm -rf "$TMP"
  unset CLAUDE_STATE_DIR CLAUDE_PLUGIN_DATA
}

_write_gear() {
  printf '%s\n' "$2" > "$CLAUDE_STATE_DIR/gear-$1"
}

@test "gear=PAIR for sid -> check_gear_gate <sid> returns 1 (skip)" {
  _write_gear "sess-abc" "PAIR"
  run check_gear_gate "sess-abc"
  [ "$status" -eq 1 ]
}

@test "gear=BUILD for sid -> check_gear_gate <sid> returns 0 (run)" {
  _write_gear "sess-abc" "BUILD"
  run check_gear_gate "sess-abc"
  [ "$status" -eq 0 ]
}

@test "gear=PIPELINE for sid -> check_gear_gate <sid> returns 0 (run)" {
  _write_gear "sess-abc" "PIPELINE"
  run check_gear_gate "sess-abc"
  [ "$status" -eq 0 ]
}

@test "gear state file absent for sid -> check_gear_gate <sid> returns 0 (run, fail-safe)" {
  run check_gear_gate "sess-never-written"
  [ "$status" -eq 0 ]
}

@test "empty sid -> check_gear_gate returns 0 (run, fail-safe, unevaluable input)" {
  _write_gear "sess-abc" "PAIR"
  run check_gear_gate ""
  [ "$status" -eq 0 ]
}

@test "gear state dir unreadable (CLAUDE_STATE_DIR points nowhere) -> check_gear_gate <sid> returns 0 (run, fail-safe)" {
  export CLAUDE_STATE_DIR="/nonexistent/unreadable-$$"
  run check_gear_gate "sess-abc"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Cross-process round-trip — the actual production condition. gear-select.sh
# writes gear-<sid> from ONE process (simulating a UserPromptSubmit hook);
# check_gear_gate reads gear-<sid> from a SEPARATE process (simulating a
# PreToolUse/CLI-invoked hook), passing the SAME session_id extracted from
# that process's own stdin JSON. This must resolve correctly even though the
# two processes have different PIDs/PPIDs — proving the fix is not an
# artifact of same-process test fixtures (the old PPID-keyed test only
# passed because writer and reader shared one PPID).
# ---------------------------------------------------------------------------

@test "CP1 cross-process: gear-select writes under stdin session_id, a SEPARATE process's check_gear_gate reads it via the same sid and gates PAIR" {
  # Separate process #1: gear-select.sh, receiving {"prompt":...,"session_id":"sess-xproc"} on stdin.
  run bash -c "source '$REPO_ROOT/hooks/_lib/gear-select.sh'; printf '{\"prompt\": \"what does this do\", \"session_id\": \"sess-xproc\"}' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]

  # Separate process #2: a gear-gated hook resolving sid from ITS OWN stdin
  # JSON (a different payload/tool call), then calling check_gear_gate.
  run bash -c "
    source '$REPO_ROOT/hooks/_lib/session-id.sh'
    source '$REPO_ROOT/hooks/_lib/gear-gate.sh'
    hook_input='{\"tool_name\":\"Bash\",\"session_id\":\"sess-xproc\"}'
    sid=\$(resolve_session_id \"\$hook_input\")
    check_gear_gate \"\$sid\"
  "
  [ "$status" -eq 1 ]
}

@test "CP2 cross-process: BUILD gear resolves to RUN (0) via the same cross-process sid path" {
  run bash -c "source '$REPO_ROOT/hooks/_lib/gear-select.sh'; printf '{\"prompt\": \"implement a new caching layer for the API\", \"session_id\": \"sess-xproc-build\"}' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "BUILD" ]

  run bash -c "
    source '$REPO_ROOT/hooks/_lib/session-id.sh'
    source '$REPO_ROOT/hooks/_lib/gear-gate.sh'
    hook_input='{\"tool_name\":\"Bash\",\"session_id\":\"sess-xproc-build\"}'
    sid=\$(resolve_session_id \"\$hook_input\")
    check_gear_gate \"\$sid\"
  "
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# CP3/CP4 — as-a-hook cross-process: gear-select.sh EXECUTED (not sourced),
# the real UserPromptSubmit invocation shape, in one process; a separate
# gear-gated hook (phase-boundary-compress.sh) EXECUTED as its own process,
# reading the marker back via the SAME session id. This is the test that
# must go RED when gear-select.sh has no script entrypoint (defines
# gear_select but never calls it on direct execution) — sourcing-based tests
# above cannot catch that gap because `source` always runs function bodies
# on call regardless of whether an entrypoint guard exists.
# ---------------------------------------------------------------------------

setup_cp_hook_env() {
  CP_TMP="$(mktemp -d -t gear-gate-cp.XXXXXX)"
  export CLAUDE_STATE_DIR="$CP_TMP/state"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$CP_TMP/harness-data"
  export CLAUDE_SESSION_ID="$1"
  mkdir -p "$CLAUDE_STATE_DIR" "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID"
}

teardown_cp_hook_env() {
  rm -rf "$CP_TMP"
  unset CLAUDE_STATE_DIR CLAUDE_PLUGIN_ROOT CLAUDE_PLUGIN_DATA CLAUDE_SESSION_ID
}

@test "CP3 as-a-hook: gear-select.sh EXECUTED writes gear-<sid> PAIR, a SEPARATE EXECUTED phase-boundary-compress.sh no-ops" {
  setup_cp_hook_env "sess-hook-pair"

  # Process #1: gear-select.sh run AS A HOOK (bash <file>, stdin JSON) —
  # the exact invocation shape hooks.json/settings.json now register.
  run bash -c "printf '{\"prompt\": \"fix a typo\", \"session_id\": \"%s\"}' '$CLAUDE_SESSION_ID' | bash '$REPO_ROOT/hooks/_lib/gear-select.sh'"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
  [ -f "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}" ]
  [ "$(cat "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}")" = "PAIR" ]

  # Process #2: a gear-gated hook run AS A HOOK (its own separate process,
  # CLI-invoked, sid resolved from $CLAUDE_SESSION_ID) — must no-op silently.
  run bash "$REPO_ROOT/hooks/phase-boundary-compress.sh" "build" "security-review"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ ! -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]

  teardown_cp_hook_env
}

@test "CP4 as-a-hook: gear-select.sh EXECUTED writes gear-<sid> PIPELINE, a SEPARATE EXECUTED phase-boundary-compress.sh runs" {
  setup_cp_hook_env "sess-hook-pipeline"

  run bash -c "printf '{\"prompt\": \"add oauth token handling\", \"session_id\": \"%s\"}' '$CLAUDE_SESSION_ID' | bash '$REPO_ROOT/hooks/_lib/gear-select.sh'"
  [ "$status" -eq 0 ]
  [ "$output" = "PIPELINE" ]
  [ -f "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}" ]
  [ "$(cat "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}")" = "PIPELINE" ]

  run bash "$REPO_ROOT/hooks/phase-boundary-compress.sh" "build" "security-review"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]

  teardown_cp_hook_env
}

@test "CP5 as-a-hook: unclassified sid (gear-select never ran for it) -> gear-gated hook still RUNS (fail-safe)" {
  setup_cp_hook_env "sess-hook-never-classified"

  run bash "$REPO_ROOT/hooks/phase-boundary-compress.sh" "build" "security-review"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]

  teardown_cp_hook_env
}

# ---------------------------------------------------------------------------
# Reverse-parity — dual-registration invariant (memory:
# dual-registration-enforcing-guard-drift). gear-select.sh only fires in a
# live session if it is registered as a UserPromptSubmit hook in BOTH
# hooks/hooks.json AND settings.json; a hook present in one registry but not
# the other is a drift bug that silently disables the classifier in
# whichever surface loads the other file.
# ---------------------------------------------------------------------------

@test "REG1 gear-select.sh is registered as a UserPromptSubmit hook in BOTH hooks.json and settings.json" {
  run python3 - "$REPO_ROOT/hooks/hooks.json" "$REPO_ROOT/settings.json" <<'PYEOF'
import json, sys

def userpromptsubmit_commands(path):
    with open(path) as f:
        d = json.load(f)
    entries = d.get("hooks", d).get("UserPromptSubmit", [])
    cmds = []
    for entry in entries:
        for h in entry.get("hooks", []):
            cmds.append(" ".join(h.get("args", [])))
    return cmds

hooks_json_cmds = userpromptsubmit_commands(sys.argv[1])
settings_json_cmds = userpromptsubmit_commands(sys.argv[2])

in_hooks_json = any("gear-select.sh" in c for c in hooks_json_cmds)
in_settings_json = any("gear-select.sh" in c for c in settings_json_cmds)

if not in_hooks_json:
    print("MISSING from hooks/hooks.json UserPromptSubmit", file=sys.stderr)
if not in_settings_json:
    print("MISSING from settings.json UserPromptSubmit", file=sys.stderr)

sys.exit(0 if (in_hooks_json and in_settings_json) else 1)
PYEOF
  [ "$status" -eq 0 ]
}
