#!/usr/bin/env bats
# WHY: Asserts that observation-length-cap.sh and all its registry/test
# pinning artifacts are gone. A new failure here means someone accidentally
# re-added the dead advisory hook that had zero telemetry across 772 sessions.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"

@test "hooks/observation-length-cap.sh is deleted" {
  run test -f "$REPO_ROOT/hooks/observation-length-cap.sh"
  [ "$status" -ne 0 ]
}

@test "tests/test_observation_length_cap_hook.py is deleted" {
  run test -f "$REPO_ROOT/tests/test_observation_length_cap_hook.py"
  [ "$status" -ne 0 ]
}

@test "hooks.json has no observation-length-cap reference" {
  run grep -c "observation-length-cap" "$REPO_ROOT/hooks/hooks.json"
  [ "$output" = "0" ]
}

@test "settings.json has no observation-length-cap reference" {
  run grep -c "observation-length-cap" "$REPO_ROOT/settings.json"
  [ "$output" = "0" ]
}
