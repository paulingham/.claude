#!/usr/bin/env bats
# Placeholder smoke test. Its only job is to prove the harness can load a
# .bats file and run a trivially-passing assertion once bats is installed.
# Real specs live alongside their slice (e.g. project-hash.bats, settings.bats).

@test "shell harness smoke: true is true" {
  [ "$(true && echo ok)" = "ok" ]
}
