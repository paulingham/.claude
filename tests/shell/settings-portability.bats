#!/usr/bin/env bats
# Portable paths in settings.json. Every absolute user path must be $HOME-
# relative so the harness moves between machines.
#
# History: an earlier nested .claude/settings.json and several env keys
# (HCOM, HF_TOKEN_PATH, PARRY_IGNORE_DIRS, HF_TOKEN) plus the `memory`
# mcpServer were retired; the assertions below track the current single
# root settings.json.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TOP="$REPO_ROOT/settings.json"
}

@test "AC2.1 no hardcoded user path in settings.json" {
  [ "$(grep -c '/Users/Paul.Ingham/' "$TOP")" = "0" ]
}

@test "AC2.2 settings.json parses as JSON" {
  python3 -m json.tool "$TOP" >/dev/null
}

@test "AC2.3 every additionalDirectory is \$HOME/.claude/..." {
  # The exact count is not pinned (it grows as the harness adds dirs); what
  # matters is that none is a hardcoded/non-$HOME path.
  [ "$(jq -r '.permissions.additionalDirectories | length' "$TOP")" -ge 1 ]
  bad="$(jq -r '.permissions.additionalDirectories[] | select(startswith("$HOME/.claude/") | not)' "$TOP")"
  [ -z "$bad" ]
}

@test "AC2.4 every \$HOME-style env/mcp path starts with \$HOME/" {
  # Only assert on keys that are actually present; retired keys are skipped.
  for key in HCOM HF_TOKEN_PATH PARRY_IGNORE_DIRS; do
    v="$(jq -r ".env.${key} // \"ABSENT\"" "$TOP")"
    [ "$v" = "ABSENT" ] && continue
    [[ "$v" == \$HOME/* ]] || { echo "env.${key}=$v"; false; }
  done
  # Any mcpServer arg that looks like an absolute path must be $HOME-relative.
  while IFS= read -r v; do
    case "$v" in
      /*) echo "absolute mcpServers arg: $v"; false ;;
    esac
  done < <(jq -r '.mcpServers // {} | to_entries[] | .value.args // [] | .[]' "$TOP")
}

@test "AC2.6 CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = \"1\"" {
  [ "$(jq -r '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS' "$TOP")" = "1" ]
}

@test "AC2.8 ORT_DYLIB_PATH is not hardcoded in settings.json" {
  # Linux binaries use .so, macOS uses .dylib — no single literal path works
  # across OSes. Bootstrap must resolve the path at runtime per OS.
  [ "$(jq -r '.env.ORT_DYLIB_PATH // "absent"' "$TOP")" = "absent" ]
}
