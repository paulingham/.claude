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
