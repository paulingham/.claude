#!/usr/bin/env bats
# Enforces portable `#!/usr/bin/env bash` shebangs across the harness.
# `#!/bin/bash` breaks on NixOS (no /bin/bash) and is fragile on Alpine
# (bash may live under /usr/bin/bash). See cross-env-portability audit H2.
#
# Two assertions:
#   1. No tracked *.sh file (excluding .claude/worktrees/) uses `#!/bin/bash`.
#   2. The shellcheck-shebang guard script correctly detects violations.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  GUARD="$REPO_ROOT/automation/check-shebangs.sh"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

@test "no file under repo root uses '#!/bin/bash' shebang" {
  # Cross-checks the guard: uses find-based selection (not git ls-files), so a
  # bug in either side would be caught by disagreement. Excludes worktrees,
  # .git, and node_modules — everywhere else gets scanned regardless of ext.
  cd "$REPO_ROOT"
  run bash -c "
    find . \
      -path ./.claude/worktrees -prune -o \
      -path ./.git -prune -o \
      -path ./node_modules -prune -o \
      -type f -print0 \
    | xargs -0 grep -l '^#!/bin/bash' 2>/dev/null || true
  "
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "check-shebangs.sh exits 0 on a clean tree" {
  [ -x "$GUARD" ]
  cd "$REPO_ROOT"
  run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "check-shebangs.sh exits non-zero when a file uses '#!/bin/bash'" {
  cd "$TMP_DIR"
  git init -q
  printf '#!/bin/bash\necho hi\n' > bad.sh
  chmod +x bad.sh
  git add bad.sh
  git -c user.email=t@t -c user.name=t commit -q -m seed
  run "$GUARD"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'bad.sh'
}

@test "check-shebangs.sh names every offending file in its output" {
  cd "$TMP_DIR"
  git init -q
  printf '#!/bin/bash\n' > one.sh
  printf '#!/bin/bash\n' > two.sh
  chmod +x one.sh two.sh
  git add one.sh two.sh
  git -c user.email=t@t -c user.name=t commit -q -m seed
  run "$GUARD"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'one.sh'
  echo "$output" | grep -q 'two.sh'
}

@test "check-shebangs.sh detects '#!/bin/bash' in .bash files" {
  cd "$TMP_DIR"
  git init -q
  printf '#!/bin/bash\necho hi\n' > profile.bash
  chmod +x profile.bash
  git add profile.bash
  git -c user.email=t@t -c user.name=t commit -q -m seed
  run "$GUARD"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'profile.bash'
}

@test "check-shebangs.sh detects '#!/bin/bash' in extensionless executables" {
  cd "$TMP_DIR"
  git init -q
  printf '#!/bin/bash\necho hi\n' > runner
  chmod +x runner
  git add runner
  git -c user.email=t@t -c user.name=t commit -q -m seed
  run "$GUARD"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'runner'
}

@test "check-shebangs.sh detects offenders with spaces in filenames" {
  cd "$TMP_DIR"
  git init -q
  printf '#!/bin/bash\n' > "has space.sh"
  chmod +x "has space.sh"
  git add "has space.sh"
  git -c user.email=t@t -c user.name=t commit -q -m seed
  run "$GUARD"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'has space.sh'
}
