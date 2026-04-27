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
  "rules/engineering-protocol.md:78"
  # "≤ 50 lines" — file-level cap (incidental "5"-in-"50" grep hit).
  "rules/engineering-protocol.md:77"
  "skills/build-implementation/SKILL.md:71"
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
  "skills/build-implementation/SKILL.md:50"
  "skills/react-native-patterns/SKILL.md:69"
  "skills/refactor/SKILL.md:73"
  # CC (cyclomatic complexity ≤ 5) — restated alongside the function-body cap.
  "scripts/README.md:88"
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
