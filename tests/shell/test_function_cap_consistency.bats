#!/usr/bin/env bats
# Cycle 3 — wave4-K-line-cap. Sweep test: no function-shape "5 lines" prose
# remains in rules/, skills/, agents/, hooks/_lib/, session-memory/, plus
# top-level CLAUDE.md, README.md, orchestrator/, hooks/ (root), scripts/.
# Allowlist captures known non-function-shape uses of "5" (CC, complexity
# budget, file counts, BM25 rank, "5"-in-"50", etc.). Each entry is a
# deliberate non-function-shape reference, audited and approved.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

# Allowlist format: "<relative-path>:<line>" — one per array entry.
# Entries here are matches the grep finds but which are NOT function-shape
# assertions and therefore must NOT be rewritten.
ALLOWLIST=(
  # CC (cyclomatic complexity) cap, not function body length.
  "rules/engineering-protocol.md:7"
  # ATDD shape-constraint restatement (wave4-R) - CC <=5 + nesting <=2.
  "rules/engineering-protocol.md:75"
  # "≤ 50 lines" — file-level cap (incidental "5"-in-"50" grep hit).
  "skills/react-native-patterns/SKILL.md:84"
  "skills/react-native-patterns/SKILL.md:85"
  "skills/react-native-patterns/SKILL.md:86"
  "skills/react-native-patterns/SKILL.md:87"
  "skills/react-native-patterns/SKILL.md:88"
  "skills/tool-synthesis/SKILL.md:72"
  # BM25 search rank threshold, not function shape.
  "skills/embedder/tests/fixtures/README.md:49"
  # Complexity Budget points (story sizing), not function shape.
  "skills/epic-breakdown/SKILL.md:53"
  # File-count threshold for slice sizing, not function shape.
  "skills/epic-breakdown/SKILL.md:74"
  # Diff size threshold for "Micro" task class, not function shape.
  "skills/pipeline/SKILL.md:33"
  # Incidental "≤ 5" match on "≤ 50 lines" — file-level cap, not function shape.
  "hooks/_lib/session-store.sh:3"
  "session-memory/adapters/README.md:126"
  "skills/internal-eval/run/lib/status.sh:3"
  # Incidental "<= 5" match on CC threshold — function-shape phrase already says "8".
  "skills/build-implementation/SKILL.md:44"
  "skills/build-implementation/SKILL.md:53"
  "skills/build-implementation/SKILL.md:74"
  "skills/react-native-patterns/SKILL.md:69"
  "skills/refactor/SKILL.md:73"
  # CC (cyclomatic complexity ≤ 5) — restated alongside the function-body cap.
  "scripts/README.md:88"
  # --- Refreshed allowlist: non-function-shape "5" uses + genuine ≤5-line-per-
  # function library contracts (enforced by their own bats LOC/shape tests, e.g.
  # cost-feed T18). None is the legacy 8-line method rule mis-stated as 5. ---
  "agents/fix-engineer.md:113"          # CC ≤ 5 restatement
  "agents/pbt-engineer.md:71"           # "first 5-line excerpt" of a tool failure
  "agents/security-engineer.md:76"      # "within ±5 lines of the finding"
  "hooks/_lib/baseline_capture.sh:86"   # CC ≤ 5
  "hooks/_lib/cost-helpers.sh:3"        # ≤5-line-per-function contract (cost-feed T18)
  "hooks/_lib/cost-jsonl-emit.py:5"     # references that contract
  "hooks/cost-feed.sh:5"                # references that contract
  "hooks/_lib/eval-capture-worker-cache.sh:7"  # bodies ≤ 5 lines, file ≤ 50
  "hooks/_lib/gh-cache-layout.sh:9"     # bodies ≤ 5 lines, file ≤ 50
  "hooks/_lib/plan-cache-lookup.sh:76"  # CC ≤ 5
  "hooks/_lib/sandbox_e2b_client.py:96" # incidental
  "hooks/_lib/sast_triage_render.py:141" # incidental
  "hooks/_lib/visual_diff.js:102"       # incidental
  "rules/core.md:22"                    # "Cyclomatic complexity ≤ 5"
  "scripts/README.md:128"              # CC ≤ 5
  "scripts/test_best_of_n_skill_structure.sh:16"   # "50 lines" file-cap hit
  "scripts/test_best_of_n_skill_structure.sh:110"
  "scripts/test_pdr_rtv_skill_structure.sh:15"
  "scripts/test_pdr_rtv_skill_structure.sh:105"
  "skills/build-implementation/SKILL.md:71"
  "skills/build-implementation/SKILL.md:80"
  "skills/build-implementation/SKILL.md:248"
  "skills/build-implementation/SKILL.md:273"
  "skills/internal-eval/capture/lib/gh-pr-cache-source.sh:7"  # bodies ≤ 5
  "skills/pipeline/SKILL.md:63"
  "skills/property-based-test/SKILL.md:109"
  "skills/tool-synthesis/SKILL.md:87"
)

@test "no function-shape '5 lines' assertions remain (non-allowlisted)" {
  cd "$REPO_ROOT"
  # Capture all current matches across the full prose+orchestrator surface.
  matches=$(git grep -nE '(5[ -]?lines?|≤ 5|<= 5)' \
    CLAUDE.md README.md \
    rules/ skills/ agents/ hooks/_lib/ session-memory/ \
    orchestrator/ hooks/ scripts/ 2>/dev/null || true)
  # Filter out allowlisted (path:line) prefixes.
  filtered="$matches"
  for entry in "${ALLOWLIST[@]}"; do
    filtered=$(echo "$filtered" | grep -v -F "$entry:" || true)
  done
  # Strip blank lines and count.
  filtered=$(echo "$filtered" | sed '/^[[:space:]]*$/d')
  count=$(echo -n "$filtered" | grep -c '^' || true)
  if [ "$count" -ne 0 ]; then
    echo "Function-shape '5 lines' references still present:"
    echo "$filtered"
    false
  fi
}
