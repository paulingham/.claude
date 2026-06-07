#!/usr/bin/env bash
# Record the STABLY-failing pytest node IDs as the quality-gate "known-red" baseline.
# _qg_check_tests_python tolerates these pre-existing failures and only blocks NEW
# regressions. Re-run this after deliberately accepting more red.
#
# This suite is NONDETERMINISTIC in full-run mode (~20 node IDs flap run-to-run from
# inter-test state pollution). To keep flappy tests OUT of the baseline, the recorder
# captures the INTERSECTION of two consecutive full runs — only node IDs that fail in
# BOTH runs are recorded. CLAUDE_QG_TEST_RUNS overrides the run count (default 2).
#
# Writes sorted node IDs + a `# recorded: <HEAD>` provenance line to:
#   ${HARNESS_DATA:-$HOME/.claude}/pipeline-state/quality-gate/known-red.txt
# This is env-local runtime state (gitignored / outside the repo) — never committed.
set -uo pipefail

_qg_baseline_path() { printf '%s/pipeline-state/quality-gate/known-red.txt' "${HARNESS_DATA:-$HOME/.claude}"; }

# One pytest run → failing node IDs. Must match _qg_pytest_failures in
# hooks/_lib/quality-gate-checks.sh exactly: -rfE surfaces FAILED + collection-ERROR
# summary lines; --continue-on-collection-errors prevents an unprovisioned optional dep
# from aborting the run and hiding the real red. rc captured via `|| true` for pipefail.
_qg_run_failures() {
  local out; out=$(pytest -q --no-header -p no:cacheprovider -o addopts="" -rfE --continue-on-collection-errors 2>/dev/null || true)
  printf '%s\n' "$out" | grep -oE '^(FAILED|ERROR|SUBFAILED[^ ]*) +tests/[^ ]+' \
    | grep -oE 'tests/[^ ]+' | sort -u
}

# Intersection of N full runs: node IDs failing in EVERY run (stably red, not flappy).
_qg_collect_stable_failures() {
  local runs="${CLAUDE_QG_TEST_RUNS:-2}" merged="" i
  for ((i = 0; i < runs; i++)); do merged=$(printf '%s\n%s\n' "$merged" "$(_qg_run_failures)"); done
  printf '%s\n' "$merged" | grep -v '^$' | sort | uniq -c | awk -v n="$runs" '$1 == n {print $2}'
}

main() {
  command -v pytest &>/dev/null || { echo "qg-baseline-record: pytest not found on PATH" >&2; return 1; }
  local path failures head; path=$(_qg_baseline_path)
  mkdir -p "$(dirname "$path")"
  failures=$(_qg_collect_stable_failures); head=$(git rev-parse HEAD 2>/dev/null || echo unknown)
  { printf '%s\n' "$failures" | grep -v '^$'; printf '# recorded: %s\n' "$head"; } > "$path"
  printf 'recorded %s stably-red tests (intersection of %s runs) to %s\n' \
    "$(printf '%s\n' "$failures" | grep -c .)" "${CLAUDE_QG_TEST_RUNS:-2}" "$path"
}

main "$@"
