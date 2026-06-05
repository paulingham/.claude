#!/usr/bin/env bats
# L3: setup.sh's prereq-check message must not hardcode Homebrew on Linux.
# On macOS point to brew.sh; on Linux point to scripts/install-tools.sh (the
# OS-aware installer introduced in slice 4).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SETUP="$REPO_ROOT/setup.sh"
}

@test "L3.1 setup.sh retains the macOS brew.sh pointer (grep-only)" {
  run grep -n 'brew.sh' "$SETUP"
  [ "$status" -eq 0 ]
}

@test "L3.2 setup.sh references scripts/install-tools.sh as the Linux path" {
  run grep -n 'scripts/install-tools.sh' "$SETUP"
  [ "$status" -eq 0 ]
}

@test "L3.3 the brew-missing branch does NOT point Linux users at brew.sh unconditionally" {
  # The raw 'install Homebrew' prose must only appear inside a Darwin-scoped
  # case/if block. We enforce this by requiring the literal prose to sit
  # beneath a 'Darwin' case arm within the same case statement.
  run awk '
    /case "\$\(uname -s\)"/{incase=1}
    incase && /Darwin\)/{indarwin=1; next}
    incase && /Linux\)/{indarwin=0}
    incase && /esac/{incase=0; indarwin=0}
    /install Homebrew/ && !indarwin {print "OFFENDER:"NR":"$0}
  ' "$SETUP"
  [ -z "$output" ] || { echo "install Homebrew referenced outside Darwin scope:"; echo "$output"; false; }
}

@test "L3.4 node remediation block does not emit brew install node" {
  # The install_node_via_manager call site must not contain 'brew install node'.
  run grep -n 'brew install node' "$SETUP"
  # grep returns 1 when no match — that is the passing condition.
  [ "$status" -ne 0 ]
}

@test "L3.5 LSP block guards idempotency before calling ensure_lsp_servers" {
  # setup.sh must check command_exists for both LSP binaries before calling
  # ensure_lsp_servers — prevents mislabelling an already-installed state as 'installed'.
  run grep -n 'typescript-language-server.*pyright\|command_exists typescript-language-server' "$SETUP"
  [ "$status" -eq 0 ]
}

@test "L3.6 brew-absent on macOS records SKIPPED not FAILED (HIGH-2 downgrade)" {
  # The brew-absent macOS branch must append to SKIPPED+=(…) and must NOT call
  # record_failed or exit 1 for the brew-absent condition.
  # Static assertion: inspect the Darwin case arm between 'Darwin)' and the
  # next ';;' for the absence of record_failed and exit 1.
  run awk '
    /case "\$\(uname -s\)"/{incase=1}
    incase && /Darwin\)/{indarwin=1; next}
    incase && /Linux\)/{indarwin=0}
    incase && /esac/{incase=0; indarwin=0}
    incase && indarwin && /SKIPPED\+=/{found_skipped=1}
    incase && indarwin && /record_failed/{print "OFFENDER:record_failed:"NR":"$0}
    incase && indarwin && /exit 1/{print "OFFENDER:exit1:"NR":"$0}
    END{if(!found_skipped) print "MISSING:SKIPPED+="}
  ' "$SETUP"
  [ -z "$output" ] || {
    echo "brew-absent Darwin arm has unexpected record_failed/exit1 or missing SKIPPED+=:"
    echo "$output"
    false
  }
}
