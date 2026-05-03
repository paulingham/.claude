#!/usr/bin/env bats
# Slice E.5 — bash-side self-test for tests/_fixtures/pipeline_state.sh.
# Locks the layout/workstream/phases/verdict semantics that shell tests
# will rely on.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/tests/_fixtures/pipeline_state.sh"
  TMP="$(mktemp -d -t psf.XXXXXX)"
}

teardown() { rm -rf "$TMP"; }

@test "default layout=new writes subdir pipeline.md and echoes its path" {
  run _psf_make_fixture --task-id=t1 "$TMP"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP/t1/pipeline.md" ]
  [ -f "$TMP/t1/pipeline.md" ]
  grep -q "task_id: t1" "$TMP/t1/pipeline.md"
  grep -q "verdict: in_progress" "$TMP/t1/pipeline.md"
}

@test "layout=legacy writes flat pipeline.md and echoes its path" {
  run _psf_make_fixture --task-id=t1 --layout=legacy "$TMP"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP/t1-pipeline.md" ]
  [ -f "$TMP/t1-pipeline.md" ]
}

@test "layout=new + workstream nests under workstreams/{ws}/{task}/{phase}.md" {
  run _psf_make_fixture --task-id=t1 --workstream=ws1 "$TMP"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP/workstreams/ws1/t1/pipeline.md" ]
  [ -f "$TMP/workstreams/ws1/t1/pipeline.md" ]
}

@test "layout=legacy + workstream uses workstreams/{ws}/{task}-{phase}.md" {
  run _psf_make_fixture --task-id=t1 --layout=legacy --workstream=ws1 "$TMP"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP/workstreams/ws1/t1-pipeline.md" ]
  [ -f "$TMP/workstreams/ws1/t1-pipeline.md" ]
}

@test "phases='pipeline build review' writes all three phases (legacy)" {
  run _psf_make_fixture --task-id=t1 --layout=legacy --phases='pipeline build review' "$TMP"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP/t1-pipeline.md" ]
  [ -f "$TMP/t1-pipeline.md" ]
  [ -f "$TMP/t1-build.md" ]
  [ -f "$TMP/t1-review.md" ]
}

@test "phases='pipeline build' writes both phases (new)" {
  run _psf_make_fixture --task-id=t1 --phases='pipeline build' "$TMP"
  [ "$status" -eq 0 ]
  [ -f "$TMP/t1/pipeline.md" ]
  [ -f "$TMP/t1/build.md" ]
}

@test "verdict=completed is recorded in frontmatter" {
  run _psf_make_fixture --task-id=t1 --verdict=completed "$TMP"
  [ "$status" -eq 0 ]
  grep -q "verdict: completed" "$TMP/t1/pipeline.md"
}

@test "missing --task-id returns 1 with diagnostic on stderr" {
  run _psf_make_fixture "$TMP"
  [ "$status" -eq 1 ]
  [[ "$output" == *"--task-id required"* ]]
}

@test "missing STATE_DIR returns 1 with diagnostic on stderr" {
  run _psf_make_fixture --task-id=t1
  [ "$status" -eq 1 ]
  [[ "$output" == *"STATE_DIR required"* ]]
}

@test "invalid layout returns 1" {
  run _psf_make_fixture --task-id=t1 --layout=bogus "$TMP"
  [ "$status" -eq 1 ]
  [[ "$output" == *"bad layout"* ]]
}

@test "phase field is set per-phase in each file" {
  _psf_make_fixture --task-id=t1 --phases='pipeline build' "$TMP" >/dev/null
  grep -q "phase: pipeline" "$TMP/t1/pipeline.md"
  grep -q "phase: build" "$TMP/t1/build.md"
}
