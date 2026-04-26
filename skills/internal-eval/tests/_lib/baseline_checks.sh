#!/usr/bin/env bash
# Story 8 baseline capture tests.

_eq() { [ "$1" = "$2" ]; }

_fixture_aggregate() {
  local out="$1"; local ts="${2:-2026-04-24T10:00:00Z}"
  cat > "$out" <<JSON
{
  "run_id": "r1", "suite": "default", "model": "opus-4-7",
  "harness_ref": "abc1234", "total_cases": 3, "passed": 2,
  "failed_diff": 1, "failed_build": 0, "failed_timeout": 0, "failed_infra": 0,
  "pass_rate": 0.667, "total_duration_sec": 12, "total_cost_usd": 0.1,
  "completed_at": "$ts",
  "case_results": [
    {"case_id": "c1", "status": "passed"},
    {"case_id": "c2", "status": "passed"},
    {"case_id": "c3", "status": "failed_diff"}
  ]
}
JSON
}

check_baseline_writer_frontmatter() {
  local score="$1"
  # shellcheck disable=SC1091
  source "$score/lib/baseline-write.sh"
  local tmp; tmp="$(mktemp -d)"
  _fixture_aggregate "$tmp/agg.json"
  write_baseline "$tmp/out.md" "$tmp/agg.json" "2026-04-24"
  assert "baseline: file exists"                is_file "$tmp/out.md"
  assert "baseline: frontmatter has harness_ref" grep -q "^harness_ref: abc1234" "$tmp/out.md"
  assert "baseline: frontmatter has model"       grep -q "^model: opus-4-7" "$tmp/out.md"
  assert "baseline: frontmatter has timestamp"   grep -q "^timestamp: " "$tmp/out.md"
  assert "baseline: frontmatter has baseline_date" grep -q "^baseline_date: 2026-04-24" "$tmp/out.md"
  assert "baseline: frontmatter has pass_rate"   grep -q "^pass_rate: 0.667" "$tmp/out.md"
  rm -rf "$tmp"
}

check_capture_baseline_writes_file() {
  local score="$1"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/eval/runs/r1" "$tmp/eval/baselines"
  _fixture_aggregate "$tmp/eval/runs/r1/aggregate.json"
  EVAL_BASELINES_DIR="$tmp/eval/baselines" EVAL_RUNS_DIR="$tmp/eval/runs" \
    bash "$score/capture-baseline.sh" --run-id r1 >/dev/null
  local expected="$tmp/eval/baselines/2026-04-24-opus-4-7.md"
  assert "capture: committed-path baseline exists" is_file "$expected"
  assert "capture: latest symlink exists"         _islink "$tmp/eval/baselines/latest-opus-4-7.md"
  rm -rf "$tmp"
}

_islink() { [ -L "$1" ]; }

check_capture_baseline_symlink_updates() {
  local score="$1"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/eval/runs/r1" "$tmp/eval/runs/r2" "$tmp/eval/baselines"
  _fixture_aggregate "$tmp/eval/runs/r1/aggregate.json" "2026-04-20T10:00:00Z"
  _fixture_aggregate "$tmp/eval/runs/r2/aggregate.json" "2026-04-24T10:00:00Z"
  EVAL_BASELINES_DIR="$tmp/eval/baselines" EVAL_RUNS_DIR="$tmp/eval/runs" \
    bash "$score/capture-baseline.sh" --run-id r1 >/dev/null
  EVAL_BASELINES_DIR="$tmp/eval/baselines" EVAL_RUNS_DIR="$tmp/eval/runs" \
    bash "$score/capture-baseline.sh" --run-id r2 >/dev/null
  local link="$tmp/eval/baselines/latest-opus-4-7.md"
  local target; target="$(readlink "$link")"
  assert "capture: symlink updated to newest"  _eq "$target" "2026-04-24-opus-4-7.md"
  rm -rf "$tmp"
}

check_baseline_per_case_table() {
  local score="$1"
  # shellcheck disable=SC1091
  source "$score/lib/baseline-write.sh"
  local tmp; tmp="$(mktemp -d)"
  _fixture_aggregate "$tmp/agg.json"
  write_baseline "$tmp/out.md" "$tmp/agg.json" "2026-04-24"
  assert "baseline: per-case header"  grep -q "## Per-Case Results" "$tmp/out.md"
  assert "baseline: row for c1"        grep -q "| c1 | passed" "$tmp/out.md"
  assert "baseline: row for c3"        grep -q "| c3 | failed_diff" "$tmp/out.md"
  rm -rf "$tmp"
}
