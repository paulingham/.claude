#!/usr/bin/env bats
# Slice D — AC D4, D5: parallel-dispatch-details.md plan-validation challenger
# spec must skip citation-alignment when `cache_hit: true` (Domain D7); architect
# spawn prompt does NOT inject cache_hit marker.
# Plan: § Slice slice-d-orchestrator-wiring.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DOC="$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

@test "D4 citation-alignment paragraph documents cache_hit: true skip" {
  # Find the line that talks about citation alignment / Plan Validation
  # challengers; verify a nearby cache_hit: true clause exists within ±5 lines.
  anchor="$(grep -n -E 'citation.alignment|citations align with recon' "$DOC" | head -1 | cut -d: -f1)"
  [ -n "$anchor" ]
  lo=$((anchor - 5))
  hi=$((anchor + 5))
  [ "$lo" -ge 1 ] || lo=1
  run sed -n "${lo},${hi}p" "$DOC"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE 'cache_hit:[[:space:]]*true'
}

@test "D4b cache_hit skip clause uses the exact marker token" {
  run grep -E 'cache_hit:[[:space:]]*true' "$DOC"
  [ "$status" -eq 0 ]
}

@test "D5 architect spawn prompt does NOT inject cache_hit marker" {
  # Extract the architect Agent({ ... }) spawn block, scoped exactly from the
  # subagent_type line down to the first '})' close marker, and assert zero
  # cache_hit occurrences inside the spawn directive itself.
  start="$(grep -n 'subagent_type: "architect"' "$DOC" | head -1 | cut -d: -f1)"
  [ -n "$start" ]
  # First '})' line at or after $start closes the spawn directive.
  end="$(awk -v s="$start" 'NR>=s && /^\}\)/{print NR; exit}' "$DOC")"
  [ -n "$end" ]
  run sed -n "${start},${end}p" "$DOC"
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q 'cache_hit'
}
