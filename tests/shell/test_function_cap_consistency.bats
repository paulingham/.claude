#!/usr/bin/env bats
# Per-language function shape: Ruby 5 / TS 12. Consistency sweep for the
# reconcile-clean-simple-rules refactor (reverses PR #40 "wave4-K", which had
# locked a single global 8-line cap). The new law is the PER-LANGUAGE contract
# (Ruby methods ≤ 5, TS/JS functions ≤ 12, Python/Go fallback) with NAMING as
# the primary cohesion gate, plus the WHY-only comment rule.
#
# This test guards four things:
#   D2a — "5 lines" is now CORRECT for Ruby, so the sweep no longer bans it.
#         Instead it asserts every surviving "5"-shape match is a deliberate,
#         allowlisted non-fossil (CC ≤ 5, ≤50-line file cap, BM25 rank, budget
#         points, error-excerpt counts, or a genuine Ruby≤5 / TS≤12 contract).
#   D2b — no "8-line-as-global-law" fossil survives. Every surviving "8"-shape
#         match is a real per-file shell shape contract (hooks/_lib/**,
#         skills/internal-eval/**, session-memory/adapters/**), the hook's own
#         documented Python/Go fallback default, or the Maestro exemption.
#   D1  — every allowlisted path still exists on disk (catches deleted-file refs
#         like the old rules/engineering-protocol.md dangling entries).
#   D3/D4/D5 — the new contract actually exists: per-language rule in core.md,
#         Simplicity + Comments sections in the SSOT, comment rule in the build
#         agent checklists, and comment-smell-check.sh wired into both registries.
#
# Sweep surface (matches the wave4-K original): CLAUDE.md README.md rules/
# skills/ agents/ hooks/_lib/ session-memory/ orchestrator/ hooks/ scripts/.
# protocols/ is NOT swept — the SSOT (engineering-invariants.md) lives there, so
# D4 asserts its sections with a targeted grep regardless of the sweep surface.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

# Allowlist format: "<relative-path>:<line>" — one per array entry.
# Each is a match the "5-shape" sweep finds that is NOT a function-shape fossil:
# cyclomatic-complexity caps, ≤50-line file caps (the regex matches "50 lines"),
# search-rank thresholds, story-budget points, error-excerpt line counts, and
# the genuine per-language Ruby≤5 / TS≤12 contract statements (which are the NEW
# law, not the old mis-stated 8-line method rule).
ALLOWLIST_5=(
  # CC ≤ 5 restatements (cyclomatic complexity, not body length).
  "agents/fix-engineer.md:115"
  "hooks/_lib/baseline_capture.sh:86"
  "hooks/_lib/plan-cache-lookup.sh:76"
  "hooks/_lib/sandbox_e2b_client.py:96"
  "hooks/_lib/visual_diff.js:102"
  "rules/core.md:24"
  "scripts/README.md:127"
  "skills/build-implementation/SKILL.md:248"
  "skills/refactor/SKILL.md:73"
  # Error-excerpt / finding-window line counts, not function shape.
  "agents/pbt-engineer.md:71"
  "agents/security-engineer.md:77"
  "hooks/_lib/sast_triage_render.py:141"
  "skills/build-implementation/SKILL.md:71"
  "skills/property-based-test/SKILL.md:109"
  # Genuine ≤5-line-per-function library shell contracts (cost-feed T18 family,
  # enforced by their own LOC/shape tests) and references to that contract.
  "hooks/_lib/cost-helpers.sh:3"
  "hooks/_lib/cost-jsonl-emit.py:5"
  "hooks/_lib/eval-capture-worker-cache.sh:7"
  "hooks/_lib/gh-cache-layout.sh:9"
  "hooks/cost-feed.sh:5"
  "skills/internal-eval/capture/lib/gh-pr-cache-source.sh:7"
  # ≤50-line file caps (regex matches "50 lines") — file-level, not function.
  "hooks/_lib/session-store.sh:3"
  "scripts/test_best_of_n_skill_structure.sh:16"
  "scripts/test_best_of_n_skill_structure.sh:110"
  "scripts/test_pdr_rtv_skill_structure.sh:15"
  "scripts/test_pdr_rtv_skill_structure.sh:105"
  "skills/internal-eval/run/lib/status.sh:3"
  "skills/react-native-patterns/SKILL.md:84"
  "skills/react-native-patterns/SKILL.md:85"
  "skills/react-native-patterns/SKILL.md:86"
  "skills/react-native-patterns/SKILL.md:87"
  "skills/react-native-patterns/SKILL.md:88"
  "skills/tool-synthesis/SKILL.md:87"
  # BM25 search-rank threshold, not function shape.
  "skills/embedder/tests/fixtures/README.md:49"
  # Complexity-budget points / file-count for slice sizing, not function shape.
  "skills/epic-breakdown/SKILL.md:53"
  "skills/epic-breakdown/SKILL.md:74"
  # Diff-size threshold for the "Micro" task class, not function shape.
  "skills/pipeline/SKILL.md:88"
  # The NEW per-language contract (Ruby ≤ 5 / TS ≤ 12) — the law, not a fossil.
  "rules/core.md:22"
  "skills/build-implementation/SKILL.md:80"
  "skills/build-implementation/SKILL.md:252"
  "skills/build-implementation/SKILL.md:273"
  "skills/build-implementation/SKILL.md:275"
  "skills/react-native-patterns/SKILL.md:69"
  "skills/refactor/SKILL.md:36"
)

# Each is a match the "8-shape" sweep finds that is a LEGIT survivor: a real
# per-file shell shape contract, the function-body hook's own documented
# Python/Go fallback default, or the Maestro exemption. None is the old global
# "8-line method" design law (slice E repointed those to the SSOT).
ALLOWLIST_8=(
  # Real ≤8-line-per-function shell contracts (enforced by their own tests).
  "hooks/_lib/quality-gate-checks.sh:4"
  "hooks/_lib/quality-gate-checks.sh:215"
  "hooks/_lib/session-store.sh:3"
  "session-memory/adapters/local.sh:3"
  "skills/internal-eval/capture/lib/case-writers.sh:2"
  "skills/internal-eval/capture/lib/meta.sh:2"
  "skills/internal-eval/run/lib/status.sh:3"
  "skills/internal-eval/tests/_lib/backfill_checks.sh:2"
  "skills/internal-eval/tests/_lib/backfill_pr_to_case.sh:2"
  "skills/internal-eval/tests/_lib/backfill_promote.sh:2"
  "skills/internal-eval/tests/_lib/checks.sh:2"
  "skills/internal-eval/tests/_lib/gate_checks.sh:2"
  "skills/internal-eval/tests/_lib/real_case_checks.sh:2"
  # The function-body hook's own documented Python/Go fallback default.
  "README.md:257"
  "hooks/function-body-check.sh:72"
  # Maestro YAML flows are exempt from the function/file limits.
  "skills/react-native-patterns/SKILL.md:198"
)

# Shared sweep surface for both prose sweeps.
sweep_paths=(CLAUDE.md README.md rules/ skills/ agents/ hooks/_lib/ \
  session-memory/ orchestrator/ hooks/ scripts/)

# Filter a "path:line:..." grep result against a "path:line" allowlist and
# return what remains after stripping blank lines.
remaining_after_allowlist() {
  local matches="$1"; shift
  local filtered="$matches"
  local entry
  for entry in "$@"; do
    filtered=$(echo "$filtered" | grep -v -F "$entry:" || true)
  done
  echo "$filtered" | sed '/^[[:space:]]*$/d'
}

@test "D1: every allowlist path exists on disk (no dangling refs)" {
  cd "$REPO_ROOT"
  local missing=""
  local entry path
  for entry in "${ALLOWLIST_5[@]}" "${ALLOWLIST_8[@]}"; do
    path="${entry%:*}"
    if [ ! -e "$path" ]; then
      missing="${missing}${entry} (path ${path})"$'\n'
    fi
  done
  if [ -n "$missing" ]; then
    echo "Allowlist references a path that no longer exists:"
    echo "$missing"
    false
  fi
}

@test "D2a: every '5-line-shape' match is an allowlisted non-fossil (Ruby 5 is now law)" {
  cd "$REPO_ROOT"
  local matches
  matches=$(git grep -nE '(5[ -]?lines?|≤ 5|<= 5)' "${sweep_paths[@]}" 2>/dev/null || true)
  local leftover
  leftover=$(remaining_after_allowlist "$matches" "${ALLOWLIST_5[@]}")
  if [ -n "$leftover" ]; then
    echo "Unexpected '5-line-shape' references (not in ALLOWLIST_5):"
    echo "$leftover"
    echo "If a line is a legit CC/file-cap/per-language-contract match, add it"
    echo "to ALLOWLIST_5 at its CURRENT line number. If it is a fossil, fix the prose."
    false
  fi
}

@test "D2b: no '8-line-as-law' fossil survives outside the real-contract allowlist" {
  cd "$REPO_ROOT"
  local matches
  matches=$(git grep -nE '(8[ -]?lines?|≤ 8|<= 8)' "${sweep_paths[@]}" 2>/dev/null || true)
  local leftover
  leftover=$(remaining_after_allowlist "$matches" "${ALLOWLIST_8[@]}")
  if [ -n "$leftover" ]; then
    echo "Unexpected '8-line-shape' references (not in ALLOWLIST_8):"
    echo "$leftover"
    echo "The global 8-line method rule is retired. A survivor must be a real"
    echo "per-file shell contract, the hook's documented fallback, or the Maestro"
    echo "exemption — else it is a fossil slice E should have repointed to the SSOT."
    false
  fi
}

@test "D3: per-language contract present in rules/core.md (Ruby 5 / TS 12 + naming-primary-gate)" {
  cd "$REPO_ROOT"
  grep -qE 'Ruby methods? > 5 lines' rules/core.md
  grep -qE 'TypeScript/JS functions > 12 lines' rules/core.md
  grep -qiE 'Naming is the primary cohesion gate' rules/core.md
}

@test "D4: Simplicity + Comments sections present in the SSOT (engineering-invariants.md)" {
  cd "$REPO_ROOT"
  grep -qE '^## Simplicity' protocols/engineering-invariants.md
  grep -qE '^## Comments' protocols/engineering-invariants.md
  # core.md mirror carries the one-liners too.
  grep -qiE "don.t complect|don.t-complect" rules/core.md
  grep -qiE 'WHY' rules/core.md
}

@test "D5: comment rule in the 5 build-agent checklists + comment hook wired in both registries" {
  cd "$REPO_ROOT"
  local agent
  for agent in software-engineer frontend-engineer database-engineer qa-engineer infrastructure-engineer; do
    grep -qiE 'comments only the WHY' "agents/$agent.md"
  done
  grep -q 'comment-smell-check.sh' settings.json
  grep -q 'comment-smell-check.sh' hooks/hooks.json
}
