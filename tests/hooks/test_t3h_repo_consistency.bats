#!/usr/bin/env bats
# Slice-E repo-wide consistency guards for the T3H feature.
#
# E3: every T[0-6] capture-group in source (non-comment) lines in
#     hooks/ orchestrator/ skills/ tests/ protocols/ is inside a widened
#     (T[0-6]|T3H) site. A bare (T[0-6]) in live code without alternation FAILS.
# E4: the ONLY -eq 7 remaining in tests/ and skills/ is the pdr-rtv tournament
#     at skills/pdr-rtv/tests/test_tournament.bats:63 (7 comparisons for 8 candidates).
#     Any other -eq 7 (un-bumped tier count guard) FAILS.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

# --- E3: no bare T[0-6] parser remains unwidened --------------------------------

@test "test_no_bare_T0_6_parser_remains_unwidened" {
  # WHY: every regex matching T[0-6] in source must be inside a (T[0-6]|T3H)
  # alternation. A bare (T[0-6]) without |T3H rejects T3H silently, breaking the
  # trimmed lane. This guard is the codified sweep the plan required before done.
  # Scope: non-comment lines only in .py/.sh/.bats/.md files.

  local bare_hits
  # Search for T\[0-6\] in non-comment, non-binary lines, excluding lines that
  # already contain the |T3H alternation. The grep -v chain:
  # 1. Exclude lines that already carry |T3H (correctly widened)
  # 2. Exclude comment lines (lines with leading # after optional whitespace)
  # 3. Exclude binary / compiled artefacts
  # 4. Exclude this test file itself (its own E3 explanation prose)
  bare_hits=$(grep -rn 'T\[0-6\]' \
    "$REPO_ROOT/hooks/" \
    "$REPO_ROOT/orchestrator/" \
    "$REPO_ROOT/skills/" \
    "$REPO_ROOT/tests/" \
    "$REPO_ROOT/protocols/" \
    --include="*.py" --include="*.sh" --include="*.bats" --include="*.md" \
    2>/dev/null \
    | grep -v 'T\[0-6\]|T3H' \
    | grep -v '^Binary' \
    | grep -v '\.pyc:' \
    | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' \
    | grep -v 'test_t3h_repo_consistency\.bats' \
    || true)

  if [ -n "$bare_hits" ]; then
    echo "FAIL: bare T[0-6] sites found (not inside (T[0-6]|T3H) alternation):"
    echo "$bare_hits"
    return 1
  fi
}

# --- E4: only pdr-rtv tournament uses -eq 7 ------------------------------------

@test "test_only_pdr_rtv_tournament_uses_eq_7" {
  # WHY: before T3H, tier count guards used -eq 7 (seven tiers T0..T6).
  # After T3H all count guards bumped to -eq 8 (eight tiers T0..T6 + T3H).
  # The ONLY legitimate -eq 7 remaining is test_tournament.bats:63
  # (7 pairwise comparisons for 8 candidates). Any other -eq 7 is an
  # un-bumped tier count guard that silently under-counts T3H.

  local tournament_file="$REPO_ROOT/skills/pdr-rtv/tests/test_tournament.bats"

  local eq7_hits
  eq7_hits=$(grep -rn '\-eq 7' \
    "$REPO_ROOT/tests/" \
    "$REPO_ROOT/skills/" \
    --include="*.bats" --include="*.sh" --include="*.py" \
    2>/dev/null \
    | grep -v '^Binary' \
    | grep -v '\.pyc:' \
    | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' \
    | grep -v 'test_t3h_repo_consistency\.bats' \
    || true)

  if [ -z "$eq7_hits" ]; then
    return 0
  fi

  local non_tournament_hits
  non_tournament_hits=$(echo "$eq7_hits" \
    | grep -v "${tournament_file}:63" \
    || true)

  if [ -n "$non_tournament_hits" ]; then
    echo "FAIL: unexpected -eq 7 outside pdr-rtv tournament at test_tournament.bats:63:"
    echo "$non_tournament_hits"
    return 1
  fi
}
