#!/usr/bin/env bats
# Slice 2: portable paths in settings.json + .claude/settings.json.
# Every /Users/Paul.Ingham/ must be $HOME/ so the harness moves between
# machines. HF_TOKEN value is an invariant — this slice must not touch it.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TOP="$REPO_ROOT/settings.json"
  NESTED="$REPO_ROOT/.claude/settings.json"
  PRE_TOKEN="/tmp/pre_hf_token"
}

@test "AC2.1 no /Users/Paul.Ingham/ in either settings file" {
  [ "$(grep -c '/Users/Paul.Ingham/' "$TOP")" = "0" ]
  [ "$(grep -c '/Users/Paul.Ingham/' "$NESTED")" = "0" ]
}

@test "AC2.2 both settings files parse as JSON" {
  python3 -m json.tool "$TOP" >/dev/null
  python3 -m json.tool "$NESTED" >/dev/null
}

@test "AC2.3 13 additionalDirectories, all \$HOME/.claude/..." {
  [ "$(jq -r '.permissions.additionalDirectories | length' "$TOP")" = "13" ]
  bad="$(jq -r '.permissions.additionalDirectories[] | select(startswith("$HOME/.claude/") | not)' "$TOP")"
  [ -z "$bad" ]
}

@test "AC2.4 env and mcpServers paths start with \$HOME/" {
  for key in HCOM HF_TOKEN_PATH PARRY_IGNORE_DIRS; do
    v="$(jq -r ".env.${key}" "$TOP")"
    [[ "$v" == \$HOME/* ]] || { echo "env.${key}=$v"; false; }
  done
  v="$(jq -r '.mcpServers.memory.args[0]' "$TOP")"
  [[ "$v" == \$HOME/* ]] || { echo "mcpServers.memory.args[0]=$v"; false; }
}

@test "AC2.6 CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = \"1\"" {
  [ "$(jq -r '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS' "$TOP")" = "1" ]
}

@test "AC2.8 ORT_DYLIB_PATH is not hardcoded in settings.json" {
  # Linux binaries use .so, macOS uses .dylib — no single literal path works
  # across OSes. Bootstrap must resolve the path at runtime per OS.
  [ "$(jq -r '.env.ORT_DYLIB_PATH // "absent"' "$TOP")" = "absent" ]
}

@test "AC2.7 HF_TOKEN value unchanged vs pre-edit capture" {
  [ -f "$PRE_TOKEN" ] || skip "pre-edit HF_TOKEN capture missing at $PRE_TOKEN"
  [ "$(jq -r '.env.HF_TOKEN' "$TOP")" = "$(cat "$PRE_TOKEN")" ]
}
