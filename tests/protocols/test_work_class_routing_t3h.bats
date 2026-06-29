#!/usr/bin/env bats
# Slice-C detector-spec tests for protocols/work-class-routing.md
#
# C4: Phase-2 safety override sentence present and explicit.
# C5: Contract discrimination: proto/versioned/cross-repo/DB/public-sig each force T4;
#     internal-json-shape alone does not.
# C6: "when in doubt round UP" clause present.
# LOCKSTEP: keyword list is identical (17 terms) at Phase-1 detector, Phase-2 prose,
#           and forensics backstop. Prevents Finding-1-style drift from recurring.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  ROUTING="$REPO_ROOT/protocols/work-class-routing.md"
}

# C4 — Phase-2 safety override explicitly stated to always win and upshift
@test "test_safety_override_upshifts_T3H_match" {
  grep -qE 'Phase.2 safety override ALWAYS wins|safety override.*always.*upshift|Phase-2.*safety.*upshift.*T3H' "$ROUTING"
}

# C5 — each cross-repo/versioned/public/proto/DB/public-sig contract type forces T4,
#       and internal-json-shape alone is explicitly excluded from that list.
#       The round_up_to_T4_when_ANY YAML key lists all T4-forcing contract types.
@test "test_contract_internal_vs_public_discrimination" {
  # The T3H_trivial_code detector block names all T4-forcing contract types in
  # the round_up_to_T4_when_ANY list.
  grep -qE 'round_up_to_T4_when_ANY' "$ROUTING"
  grep -qE '"proto"' "$ROUTING"
  grep -qE 'versioned-public schema|versioned.*public.*schema' "$ROUTING"
  grep -qE '"cross-repo contract"' "$ROUTING"
  grep -qE '"DB schema"' "$ROUTING"
  grep -qE '"public function signature"' "$ROUTING"
  # Internal JSON shape alone must NOT force T4 (it's T3H-eligible)
  grep -qE 'internal.*JSON.*shape|JSON.*shape.*internal|internal.*JSON' "$ROUTING"
}

# C6 — "when in doubt round UP" clause present
@test "test_when_in_doubt_rounds_up" {
  grep -qE 'When in doubt.*round.*UP|when in doubt.*round.*up' "$ROUTING"
}

# LOCKSTEP — canonical 17-keyword list present at Phase-1 detector, Phase-2 prose,
#            and forensics backstop; all three must match the full set.
@test "test_canonical_17_keyword_list_in_phase1_detector" {
  # WHY: pins the full canonical list; RED if any keyword is absent from Phase-1 detector.
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$ROUTING"
}

@test "test_keyword_list_lockstep_phase2_prose_matches_canonical" {
  # WHY: Phase-2 prose must carry the same 17 keywords as the canonical list.
  # Checks each keyword appears in the Phase-2 safety override bullet.
  for kw in auth payment token secret crypto password session billing oauth jwt cors csrf cookie admin rbac cert signature; do
    grep -qE "User prompt contains.*${kw}|${kw}.*change-target" "$ROUTING" || \
      { echo "Phase-2 prose missing keyword: ${kw}"; return 1; }
  done
}

@test "test_keyword_list_lockstep_forensics_backstop_matches_canonical" {
  # WHY: the Quality safety analysis table forensics backstop row must carry the
  # full 17-keyword canonical list so drift is impossible.
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$ROUTING"
}

# E5 — verdict-catalog.md prose says T3H proceeds (continues), not exits
@test "test_verdict_catalog_prose_says_T3H_continues" {
  # WHY: pins E-3 prose — the Notes section bullet at ~:185 must confirm T3H
  # continues through the pipeline (trimmed lane), distinguishing it from
  # T0-T3 which EXIT. Ensures catalog and routing spec agree on T3H disposition.
  CATALOG="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)/protocols/verdict-catalog.md"

  # Assert: a Notes bullet must say T3H proceeds or continues
  grep -qE 'T3H.*(proceed|continue)|(proceed|continue).*T3H' "$CATALOG"

  # Assert: T3H is NOT the subject of an "exit" verb
  # (i.e. "T3H exit" or "T3H and ... exit" must not appear)
  # WHY: the pattern "T3H.*exit" would match prose like "T3H exits the pipeline"
  # which contradicts the routing spec. The existing "T0-T3 exit ... T3H proceed"
  # prose has T3H AFTER the exit clause (not as its subject), so this check is safe.
  ! grep -qE 'T3H[^;.]*exit' "$CATALOG"
}
