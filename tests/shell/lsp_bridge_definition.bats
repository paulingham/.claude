#!/usr/bin/env bats
# LSP go-to-definition bridge — CI gate.
#
# Runs WITHOUT a real LS binary by stripping the PATH of any LS executables
# (typescript-language-server, pyright-langserver, pyright, tsserver).
# Tests are hermetic and fast; they test the advisory-error path (AC1) and
# the JSON-RPC contract (AC2, AC3).  The real-binary path lives in pytest
# (AC5) and is @skipUnless-guarded.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SERVER="$REPO_ROOT/hooks/_lib/lsp-bridge-server.py"

  # Build a PATH with python3 + essential POSIX utilities but NO LS binaries.
  # WHY: we must test the ls-unavailable path without a real binary, while
  # keeping rm/ln/mktemp available in teardown.
  SAFE_DIR="$(mktemp -d)"
  ORIG_PATH="$PATH"
  for bin in python3 rm ln mkdir mktemp; do
    src="$(PATH="$ORIG_PATH" command -v "$bin" 2>/dev/null)" || continue
    ln -sf "$src" "$SAFE_DIR/$bin"
  done
  export PATH="$SAFE_DIR"
}

teardown() {
  export PATH="$ORIG_PATH"
  rm -rf "$SAFE_DIR"
}

_send_ts() {
  printf '%s\n' "$1" | python3 "$SERVER" --language ts
}

_send_py() {
  printf '%s\n' "$1" | python3 "$SERVER" --language py
}

# ---------------------------------------------------------------------------
# AC2: tools/list returns BOTH definition AND diagnostics tool names
# ---------------------------------------------------------------------------

@test "AC2: tools/list (ts) contains mcp_lsp_definition_ts" {
  req='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"mcp_lsp_definition_ts"* ]]
}

@test "AC2: tools/list (ts) still contains mcp_lsp_diagnostics_ts" {
  req='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"mcp_lsp_diagnostics_ts"* ]]
}

@test "AC2: tools/list (py) contains mcp_lsp_definition_py" {
  req='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
  run _send_py "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"mcp_lsp_definition_py"* ]]
}

@test "AC2: diagnostics tools/call still returns stub text (no-regress)" {
  req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mcp_lsp_diagnostics_ts","arguments":{"path":"x.ts"}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"advisory: LSP shell-out not yet implemented"* ]]
}

@test "AC2: diagnostics tools/call isError is false (no-regress)" {
  req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mcp_lsp_diagnostics_ts","arguments":{"path":"x.ts"}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"isError": false'* ]] || [[ "$output" == *'"isError":false'* ]]
}

# ---------------------------------------------------------------------------
# AC1: LS absent -> structured advisory error (PRIMARY CI path)
# ---------------------------------------------------------------------------

@test "AC1: definition call (ts) with LS absent returns isError true" {
  req='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"mcp_lsp_definition_ts","arguments":{"path":"x.ts","line":1,"character":5}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"isError": true'* ]] || [[ "$output" == *'"isError":true'* ]]
}

@test "AC1: definition call (ts) with LS absent returns ls-unavailable error code" {
  req='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"mcp_lsp_definition_ts","arguments":{"path":"x.ts","line":1,"character":5}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ls-unavailable"* ]]
}

@test "AC1: definition call (py) with LS absent returns isError true" {
  req='{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"mcp_lsp_definition_py","arguments":{"path":"a.py","line":0,"character":0}}}'
  run _send_py "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"isError": true'* ]] || [[ "$output" == *'"isError":true'* ]]
}

@test "AC1: definition call (py) with LS absent returns ls-unavailable error code" {
  req='{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"mcp_lsp_definition_py","arguments":{"path":"a.py","line":0,"character":0}}}'
  run _send_py "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ls-unavailable"* ]]
}

# ---------------------------------------------------------------------------
# AC3: structured errors for unsupported tool name
# ---------------------------------------------------------------------------

@test "AC3: unsupported tool name returns isError true" {
  req='{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"mcp_lsp_definition_rb","arguments":{"path":"x.rb","line":1,"character":5}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"isError": true'* ]] || [[ "$output" == *'"isError":true'* ]]
}

@test "AC3: unsupported tool name returns 'unsupported' error code" {
  req='{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"mcp_lsp_definition_rb","arguments":{"path":"x.rb","line":1,"character":5}}}'
  run _send_ts "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *"unsupported"* ]]
}
