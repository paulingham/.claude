#!/usr/bin/env bats
# Specs for scripts/_lib/install-node.sh
# Hermetic: CLAUDE_NODE_HAS_NODE, CLAUDE_NODE_PRINTER, CLAUDE_NODE_FORCE_NVM_PRESENT,
# CLAUDE_NODE_FORCE_FNM_PRESENT, CLAUDE_NODE_FORCE_INSTALL_FAIL, NVM_DIR.
# Zero network access — PRINTER short-circuits before any real command runs.
# nvm is a shell function sourced from $NVM_DIR/nvm.sh; tests inject a stub.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"

  # Create a stub NVM_DIR with a nvm.sh that defines nvm as a function
  # capturing commands via CLAUDE_NODE_PRINTER.
  NVM_STUB_DIR="$TMP_DIR/nvm_home"
  mkdir -p "$NVM_STUB_DIR"
  cat > "$NVM_STUB_DIR/nvm.sh" <<'NVMSTUB'
# Stub nvm.sh: defines nvm as a shell function
nvm() {
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "nvm $*"
    # Simulate NVM_BIN being set after 'nvm use'
    if [[ "$1" == "use" ]]; then
      export NVM_BIN="$NVM_STUB_DIR/stub_bin"
    fi
    return 0
  fi
  echo "nvm $*"
}
export -f nvm 2>/dev/null || true
NVMSTUB
  chmod +x "$NVM_STUB_DIR/nvm.sh"
}

teardown() {
  rm -rf "$TMP_DIR"
}

# Helper: stub fnm in TMP_DIR/bin
_make_fnm_stub() {
  mkdir -p "$TMP_DIR/bin"
  cat > "$TMP_DIR/bin/fnm" <<'FNM'
#!/bin/sh
case "$1" in
  env) echo "export PATH=\"$PATH\"" ;;
  *) echo "fnm $*" ;;
esac
FNM
  chmod +x "$TMP_DIR/bin/fnm"
}

# ---------- idempotency ----------

@test "install_node_via_manager: node already present -> no-op (rc 0, no PRINTER output)" {
  run bash -c "export CLAUDE_NODE_HAS_NODE=1; export CLAUDE_NODE_PRINTER=echo; source '$LIB_DIR/install-node.sh'; install_node_via_manager macos"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------- nvm present path ----------

@test "install_node_via_manager: FORCE_NVM_PRESENT -> emits nvm install --lts (no brew token)" {
  run bash -c "
    export CLAUDE_NODE_PRINTER=echo
    export CLAUDE_NODE_FORCE_NVM_PRESENT=1
    export NVM_DIR='$NVM_STUB_DIR'
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager macos
  "
  [ "$status" -eq 0 ]
  [[ "$output" == *"nvm install"* ]]
  [[ "$output" == *"lts"* ]]
  [[ "$output" != *"brew"* ]]
}

# ---------- fnm present path ----------

@test "install_node_via_manager: FORCE_FNM_PRESENT -> emits fnm install (no brew token)" {
  _make_fnm_stub
  run bash -c "
    export CLAUDE_NODE_PRINTER=echo
    export CLAUDE_NODE_FORCE_FNM_PRESENT=1
    export PATH='$TMP_DIR/bin:/usr/bin:/bin'
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager macos
  "
  [ "$status" -eq 0 ]
  [[ "$output" == *"fnm"* ]]
  [[ "$output" != *"brew"* ]]
}

# ---------- no manager -> curl nvm installer ----------

@test "install_node_via_manager: no manager -> emits curl nvm installer (no brew token)" {
  run bash -c "
    export CLAUDE_NODE_PRINTER=echo
    export PATH='/nowhere:/usr/bin:/bin'
    export NVM_DIR='$TMP_DIR/nonexistent_nvm'
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager macos
  "
  [ "$status" -eq 0 ]
  [[ "$output" == *"curl"* ]]
  [[ "$output" != *"brew"* ]]
}

# ---------- no-brew invariant on install-from-scratch path ----------

@test "install_node_via_manager: no manager, no brew token in any emitted command" {
  run bash -c "
    export CLAUDE_NODE_PRINTER=echo
    export PATH='/nowhere:/usr/bin:/bin'
    export NVM_DIR='$TMP_DIR/nonexistent_nvm'
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager ubuntu
  "
  [ "$status" -eq 0 ]
  [[ "$output" != *"brew"* ]]
}

# ---------- FORCE_INSTALL_FAIL -> rc 1 ----------

@test "install_node_via_manager: FORCE_INSTALL_FAIL -> returns non-zero (continue-on-failure)" {
  run bash -c "
    export CLAUDE_NODE_FORCE_INSTALL_FAIL=1
    export PATH='/nowhere:/usr/bin:/bin'
    export NVM_DIR='$TMP_DIR/nonexistent_nvm'
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager macos
  "
  [ "$status" -ne 0 ]
}

# ---------- nvm sourced as function via NVM_DIR fixture ----------

@test "install_node_via_manager: nvm present (NVM_DIR fixture with stub nvm.sh) -> sources nvm.sh not binary" {
  run bash -c "export CLAUDE_NODE_PRINTER=echo; export CLAUDE_NODE_FORCE_NVM_PRESENT=1; export NVM_DIR='$NVM_STUB_DIR'; export PATH='/nowhere:/usr/bin:/bin'; source '$LIB_DIR/install-node.sh'; install_node_via_manager macos"
  [ "$status" -eq 0 ]
  # Must emit nvm commands (function was sourced) not a binary call
  [[ "$output" == *"nvm"* ]]
}

# ---------- NVM_BIN unset after nvm use -> PATH export via fallback ----------

@test "install_node_via_manager: nvm present + NVM_BIN unset after use -> PATH-export via nvm-which fallback" {
  # This test exercises the real (non-PRINTER) branch of _node_install_via_nvm.
  # The stub nvm.sh defines nvm as a real function: install/use succeed without
  # setting NVM_BIN, and 'which current' returns a known path so the fallback
  # block runs.  No PRINTER is set so the guard-clause short-circuit is skipped.
  local nvm_no_bin_dir="$TMP_DIR/nvm_no_bin"
  local fake_bin="$TMP_DIR/fake_bin"
  mkdir -p "$nvm_no_bin_dir" "$fake_bin"
  # Place a stub node in fake_bin so the PATH export is testable
  printf '#!/bin/sh\necho "fake-node"\n' > "$fake_bin/node"
  chmod +x "$fake_bin/node"
  # nvm stub: install and use succeed; which returns the fake_bin path; NVM_BIN never set
  cat > "$nvm_no_bin_dir/nvm.sh" <<NVMSTUB2
nvm() {
  case "\$1" in
    install) return 0 ;;
    use)     return 0 ;;
    which)   echo "$fake_bin/node" ;;
    *)       return 0 ;;
  esac
}
NVMSTUB2
  run bash -c "
    export CLAUDE_NODE_FORCE_NVM_PRESENT=1
    export NVM_DIR='$nvm_no_bin_dir'
    export PATH='/nowhere:/usr/bin:/bin'
    unset NVM_BIN
    source '$LIB_DIR/install-node.sh'
    install_node_via_manager macos
    echo \"PATH_CONTAINS::\$PATH\"
  "
  [ "$status" -eq 0 ]
  # The fallback block should have prepended fake_bin to PATH
  [[ "$output" == *"PATH_CONTAINS::"* ]]
  [[ "$output" == *"$fake_bin"* ]]
}
