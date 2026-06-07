#!/usr/bin/env bats
# Specs for scripts/_lib/install-lsp-servers.sh
# Hermetic: CLAUDE_LSP_HAS_TSSERVER, CLAUDE_LSP_HAS_PYRIGHT, CLAUDE_LSP_PRINTER.
# Zero network access — PRINTER short-circuits before npm runs.
# npm stub injected via PATH.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

# Helper: create an npm stub in TMP_DIR/bin
_make_npm_stub() {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "npm $*"\n' > "$TMP_DIR/bin/npm"
  chmod +x "$TMP_DIR/bin/npm"
}

# ---------- both absent -> install both ----------

@test "ensure_lsp_servers: both absent -> emits npm install -g typescript-language-server" {
  _make_npm_stub
  run bash -c "export CLAUDE_LSP_PRINTER=echo; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -eq 0 ]
  [[ "$output" == *"typescript-language-server"* ]]
}

@test "ensure_lsp_servers: both absent -> emits npm install -g pyright" {
  _make_npm_stub
  run bash -c "export CLAUDE_LSP_PRINTER=echo; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -eq 0 ]
  [[ "$output" == *"pyright"* ]]
}

# ---------- partial skip: tsserver present, pyright absent ----------

@test "ensure_lsp_servers: tsserver present + pyright absent -> emits only pyright install" {
  _make_npm_stub
  run bash -c "export CLAUDE_LSP_PRINTER=echo; export CLAUDE_LSP_HAS_TSSERVER=1; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -eq 0 ]
  [[ "$output" != *"typescript-language-server"* ]]
  [[ "$output" == *"pyright"* ]]
}

# ---------- both present -> no PRINTER output (full skip) ----------

@test "ensure_lsp_servers: both present -> no PRINTER output (full skip)" {
  run bash -c "export CLAUDE_LSP_PRINTER=echo; export CLAUDE_LSP_HAS_TSSERVER=1; export CLAUDE_LSP_HAS_PYRIGHT=1; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------- no-brew invariant ----------

@test "ensure_lsp_servers: no brew token in any emitted npm install command" {
  _make_npm_stub
  run bash -c "export CLAUDE_LSP_PRINTER=echo; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -eq 0 ]
  [[ "$output" != *"brew"* ]]
}

# ---------- npm absent -> rc 1 ----------

@test "ensure_lsp_servers: npm absent -> returns non-zero (continue-on-failure)" {
  run bash -c "export PATH='/nowhere:/usr/bin:/bin'; source '$LIB_DIR/install-lsp-servers.sh'; ensure_lsp_servers"
  [ "$status" -ne 0 ]
}
