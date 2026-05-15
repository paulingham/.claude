#!/usr/bin/env bash
# Story 9 — PR body eval-baseline stamp checks.

_stamp_fixture_baseline() {
  local dir="$1"; local file="$2"
  mkdir -p "$dir"
  cat > "$dir/$file" <<'MD'
---
baseline_date: 2026-04-24
model: opus-4-5
harness_ref: abc1234
timestamp: 2026-04-24T10:00:00Z
run_id: r1
suite: default
total_cases: 10
pass_rate: 0.8
passed: 8
failed_diff: 1
failed_build: 0
failed_timeout: 1
failed_infra: 0
---

## Per-Case Results
MD
  (cd "$dir" && rm -f "latest-opus-4-5.md" && ln -s "$file" "latest-opus-4-5.md")
}

check_stamp_stub_when_no_baseline() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  local out; out="$(EVAL_BASELINES_DIR="$tmp/empty" bash "$score/stamp-pr-body.sh")"
  assert "stamp: stub contains 'not yet captured'" grep -q "not yet captured" <<<"$out"
  assert "stamp: stub references /internal-eval run" grep -q "/internal-eval run" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_emits_section_with_baseline() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _stamp_fixture_baseline "$tmp/baselines" "2026-04-24-opus-4-5.md"
  local out; out="$(EVAL_BASELINES_DIR="$tmp/baselines" bash "$score/stamp-pr-body.sh")"
  assert "stamp: contains '## Eval Baseline' header" grep -q "^## Eval Baseline" <<<"$out"
  assert "stamp: contains pass_rate"   grep -q "Pass rate.*0.8" <<<"$out"
  assert "stamp: contains case count"  grep -q "8/10 cases passed" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_has_harness_ref_timestamp_date() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _stamp_fixture_baseline "$tmp/baselines" "2026-04-24-opus-4-5.md"
  local out; out="$(EVAL_BASELINES_DIR="$tmp/baselines" bash "$score/stamp-pr-body.sh")"
  assert "stamp: contains harness_ref"    grep -q "Harness ref.*abc1234" <<<"$out"
  assert "stamp: contains baseline_date"  grep -q "Baseline date.*2026-04-24" <<<"$out"
  assert "stamp: contains model"          grep -q "Model.*opus-4-5" <<<"$out"
  assert "stamp: contains Stamped at"     grep -q "Stamped at" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_baseline_file_link() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _stamp_fixture_baseline "$tmp/baselines" "2026-04-24-opus-4-5.md"
  local out; out="$(EVAL_BASELINES_DIR="$tmp/baselines" bash "$score/stamp-pr-body.sh")"
  assert "stamp: includes baseline file path" \
    grep -q "eval/baselines/2026-04-24-opus-4-5.md" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_methodology_disclaimer() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _stamp_fixture_baseline "$tmp/baselines" "2026-04-24-opus-4-5.md"
  local out; out="$(EVAL_BASELINES_DIR="$tmp/baselines" bash "$score/stamp-pr-body.sh")"
  assert "stamp: disclaims non-SWE-bench"  grep -qi "not SWE-bench" <<<"$out"
  assert "stamp: points to methodology"    grep -q "skills/internal-eval" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_missing_field_graceful() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/baselines"
  cat > "$tmp/baselines/2026-04-24-opus-4-5.md" <<'MD'
---
baseline_date: 2026-04-24
model: opus-4-5
harness_ref: abc1234
timestamp: 2026-04-24T10:00:00Z
pass_rate: 0.5
passed: 1
total_cases: 2
---
MD
  (cd "$tmp/baselines" && ln -s "2026-04-24-opus-4-5.md" "latest-opus-4-5.md")
  local out rc; out="$(EVAL_BASELINES_DIR="$tmp/baselines" bash "$score/stamp-pr-body.sh" 2>&1)"; rc=$?
  assert "stamp: exits 0 despite missing optional fields"  _eq "$rc" "0"
  assert "stamp: still renders pass rate"                  grep -q "Pass rate.*0.5" <<<"$out"
  rm -rf "$tmp"
}

check_stamp_honours_model_arg() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/baselines"
  cat > "$tmp/baselines/2026-04-24-sonnet-4-6.md" <<'MD'
---
baseline_date: 2026-04-24
model: sonnet-4-6
harness_ref: def5678
timestamp: 2026-04-24T11:00:00Z
pass_rate: 0.9
passed: 9
total_cases: 10
---
MD
  (cd "$tmp/baselines" && ln -s "2026-04-24-sonnet-4-6.md" "latest-sonnet-4-6.md")
  local out; out="$(EVAL_BASELINES_DIR="$tmp/baselines" \
    bash "$score/stamp-pr-body.sh" --model sonnet-4-6)"
  assert "stamp: uses model arg"  grep -q "Model.*sonnet-4-6" <<<"$out"
  assert "stamp: uses ref of model arg"  grep -q "def5678" <<<"$out"
  rm -rf "$tmp"
}
