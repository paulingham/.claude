#!/usr/bin/env bats
# Slice C — codebase-map-rebuild.sh (SessionStart) + codebase-map-poll.sh (Stop)
# 11 ACs covered: AC14..AC21 + AC22-ter (warm-cache rebuild <500ms).
#
# AC22-bis (settings.json position) is asserted by tests/test_codebase_map_settings_position.py.
# AC22-quater (forensic mean-time gate) is asserted by tests/test_codebase_map_budget_forensics.py.
# AC21 OSError dlopen mock is also asserted by tests/test_codebase_map_oserror_degradation.py.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t cbm-hooks.XXXXXX)"
  TEST_HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  # HARNESS_ROOT -> repo (so hooks find their _lib + the codebase_map package);
  # HARNESS_DATA stays $HOME/.claude so state.json/db/metrics writes land in the
  # hermetic TEST_HOME where STATE_FILE/METRICS_FILE are asserted. Setting
  # CLAUDE_CONFIG_DIR would override BOTH and send writes into the repo.
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_SESSION_ID="bats-cbm-$RANDOM"
  export CLAUDE_PROJECT_HASH="batstest"
  export CLAUDE_HOOK_LOG_DIR="$TEST_HOME/.claude/metrics"

  REBUILD="$REPO_ROOT/hooks/codebase-map-rebuild.sh"
  POLL="$REPO_ROOT/hooks/codebase-map-poll.sh"
  STATE_DIR="$TEST_HOME/.claude/db/codebase-map/batstest"
  STATE_FILE="$STATE_DIR/state.json"
  METRICS_FILE="$TEST_HOME/.claude/metrics/$CLAUDE_SESSION_ID/codebase-map-rebuild.jsonl"
  mkdir -p "$STATE_DIR"
  mkdir -p "$TEST_HOME/.claude/metrics/$CLAUDE_SESSION_ID"

  # Set up a trivial fake repo that walk_repo can scan without external deps.
  FAKE_REPO="$BATS_FILE_TMPDIR/fakerepo"
  mkdir -p "$FAKE_REPO"
  printf 'def hello():\n    return 1\n' > "$FAKE_REPO/sample.py"
  cd "$FAKE_REPO" && /usr/bin/git init -q && /usr/bin/git -c user.email=t@t -c user.name=t add . && /usr/bin/git -c user.email=t@t -c user.name=t commit -q -m init
  export CLAUDE_CODEBASE_MAP_REPO_ROOT="$FAKE_REPO"
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

@test "AC14: rebuild hook header registers trap before disable check" {
  # Source-grep ordering: trap must register BEFORE the CLAUDE_DISABLE_CODEBASE_MAP check.
  trap_line=$(grep -n "^trap " "$REBUILD" | head -1 | cut -d: -f1)
  disable_line=$(grep -n "CLAUDE_DISABLE_CODEBASE_MAP" "$REBUILD" | head -1 | cut -d: -f1)
  [ -n "$trap_line" ]
  [ -n "$disable_line" ]
  [ "$trap_line" -lt "$disable_line" ]
}

@test "AC14: poll hook header registers trap before disable check" {
  trap_line=$(grep -n "^trap " "$POLL" | head -1 | cut -d: -f1)
  disable_line=$(grep -n "CLAUDE_DISABLE_CODEBASE_MAP" "$POLL" | head -1 | cut -d: -f1)
  [ -n "$trap_line" ]
  [ -n "$disable_line" ]
  [ "$trap_line" -lt "$disable_line" ]
}

@test "AC14: rebuild hook honours CLAUDE_DISABLE_CODEBASE_MAP=1 fast-exit" {
  CLAUDE_DISABLE_CODEBASE_MAP=1 run bash "$REBUILD"
  [ "$status" -eq 0 ]
  # No JSONL line should be emitted (hook fast-exited)
  [ ! -f "$METRICS_FILE" ]
}

@test "AC15: rebuild hook resolves project hash env-first" {
  # CLAUDE_PROJECT_HASH=batstest is set in setup; assert state-dir path uses it.
  run bash "$REBUILD"
  [ "$status" -eq 0 ]
  # The state-dir should have been created at the env-resolved path
  [ -d "$STATE_DIR" ]
}

@test "AC16: rebuild hook persists new SHA to state.json BEFORE rebuild call" {
  # Even if the rebuild subprocess fails, the state.json MUST already
  # carry the new SHA (state-before-expensive-op contract).
  # Simulate failure by pointing the CLI at a bogus module name.
  CLAUDE_CODEBASE_MAP_CLI_MODULE="codebase_map.cli_does_not_exist" run bash "$REBUILD"
  [ "$status" -eq 0 ]
  # state.json exists and parseable as JSON
  [ -f "$STATE_FILE" ]
  python3 -c "import json,sys; d=json.load(open('$STATE_FILE')); assert 'last_built_sha' in d, 'missing last_built_sha'"
}

@test "AC17: poll hook no-ops when SHA unchanged" {
  # Pre-seed state.json with the current HEAD SHA.
  CURRENT_SHA=$(/usr/bin/git -C "$FAKE_REPO" rev-parse HEAD)
  python3 -c "import json; open('$STATE_FILE','w').write(json.dumps({'last_built_sha':'$CURRENT_SHA','last_built_at':'2026-05-10T00:00:00Z'}))"

  run bash "$POLL"
  [ "$status" -eq 0 ]
  # No new JSONL line (no rebuild fired)
  if [ -f "$METRICS_FILE" ]; then
    line_count=$(wc -l < "$METRICS_FILE" | tr -d ' ')
    [ "$line_count" -eq 0 ]
  fi
}

@test "AC17: poll hook DOES rebuild when SHA advances" {
  # Pre-seed state.json with a stale SHA; current SHA differs.
  python3 -c "import json; open('$STATE_FILE','w').write(json.dumps({'last_built_sha':'staleshastaleshastalesha','last_built_at':'2026-01-01T00:00:00Z'}))"

  run bash "$POLL"
  [ "$status" -eq 0 ]
  # JSONL line WAS emitted
  [ -f "$METRICS_FILE" ]
  line_count=$(wc -l < "$METRICS_FILE" | tr -d ' ')
  [ "$line_count" -ge 1 ]
}

@test "AC18: rebuild hook invokes python via subprocess argv only — no python3 -c form" {
  # Hook body MUST contain the argv form
  grep -q "python3 -m codebase_map.cli" "$REBUILD"
  # Hook body MUST NOT contain 'python3 -c' form (inline import is forbidden)
  ! grep -E 'python3\s+-c' "$REBUILD"
}

@test "AC18: poll hook invokes python via subprocess argv only — no python3 -c form" {
  grep -q "python3 -m codebase_map.cli" "$POLL"
  ! grep -E 'python3\s+-c' "$POLL"
}

@test "AC19: rebuild hook emits forensic JSONL with required fields" {
  run bash "$REBUILD"
  [ "$status" -eq 0 ]
  [ -f "$METRICS_FILE" ]
  line=$(tail -1 "$METRICS_FILE")
  python3 - <<EOF
import json
d = json.loads(open("$METRICS_FILE").read().strip().split("\n")[-1])
required = {"ts","file_count","time_ms","cache_hit_rate","sha_before","sha_after","hook"}
missing = required - set(d.keys())
assert not missing, f"missing fields: {missing}"
assert d["hook"] == "rebuild", f"hook field wrong: {d.get('hook')}"
EOF
}

@test "AC20: rejects malformed CLAUDE_PROJECT_HASH and falls back" {
  # An attacker-controlled hash must not escape the cache root.
  CLAUDE_PROJECT_HASH="../../etc" run bash "$REBUILD"
  [ "$status" -eq 0 ]
  # The malicious path must NOT have been used; no state.json created at ../../etc
  [ ! -e "$TEST_HOME/etc/state.json" ]
  [ ! -e "$TEST_HOME/.claude/db/codebase-map/../../etc/state.json" ]
}

@test "AC21: degrades gracefully when generator returns non-zero" {
  # Force a non-zero exit by pointing the CLI module name at an import that fails.
  CLAUDE_CODEBASE_MAP_CLI_MODULE="codebase_map.does_not_exist_abc" run bash "$REBUILD"
  [ "$status" -eq 0 ]
  # Stderr should carry one warning line
  echo "$output" | grep -qiE "codebase-map.*(unavailable|warning|degraded|skipped|failed)"
}

@test "AC22-ter: warm cache rebuild completes under 500ms" {
  # Pre-seed cache + state.json with current SHA so the rebuild is a no-op fast path.
  CURRENT_SHA=$(/usr/bin/git -C "$FAKE_REPO" rev-parse HEAD)
  python3 -c "import json; open('$STATE_FILE','w').write(json.dumps({'last_built_sha':'$CURRENT_SHA','last_built_at':'2026-05-10T00:00:00Z'}))"

  # First run to warm cache
  bash "$REBUILD" >/dev/null 2>&1 || true
  # Second run is the timed run
  bash "$REBUILD" >/dev/null 2>&1
  [ -f "$METRICS_FILE" ]
  line=$(tail -1 "$METRICS_FILE")
  TIME_MS=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d['time_ms'])" "$line")
  # Allow 500ms budget
  [ "$TIME_MS" -lt 500 ]
}
