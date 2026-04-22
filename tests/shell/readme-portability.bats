#!/usr/bin/env bats
# Slice 6: README documents cloud portability, session isolation, and the
# Ubuntu clone-and-run flow. These sections are the onboarding contract
# for a fresh Ubuntu 24.04 box — every reference must be grep-assertable
# so the instructions cannot silently drift from the artifacts they cite.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  README="$REPO_ROOT/README.md"
}

@test "AC6.1 three new H2 sections exist exactly once" {
  [ "$(grep -c '^## Cloud portability$' "$README")" = "1" ]
  [ "$(grep -c '^## Session isolation$' "$README")" = "1" ]
  [ "$(grep -c '^## Ubuntu clone-and-run$' "$README")" = "1" ]
}

@test "AC6.2 each section references its concrete artifact path" {
  cloud="$(awk '/^## Cloud portability$/{f=1;next} f && /^## /{f=0} f' "$README")"
  echo "$cloud" | grep -q 'scripts/install-tools.sh'
  session="$(awk '/^## Session isolation$/{f=1;next} f && /^## /{f=0} f' "$README")"
  echo "$session" | grep -q 'knowledge/session-isolation-patterns.md'
  echo "$session" | grep -q 'scripts/new-session.sh'
  ubuntu="$(awk '/^## Ubuntu clone-and-run$/{f=1;next} f && /^## /{f=0} f' "$README")"
  echo "$ubuntu" | grep -q 'scripts/install-tools.sh'
}

@test "AC6.3 Ubuntu section contains exactly three shell commands" {
  count="$(awk '/^## Ubuntu clone-and-run$/{f=1;next} f && /^## /{f=0} f' "$README" \
    | grep -cE '^(bash |git clone )')"
  [ "$count" = "3" ]
}

@test "AC6.4 no markdown linter configured or linter passes" {
  if command -v markdownlint >/dev/null 2>&1; then
    markdownlint "$README"
  else
    skip "no markdownlint configured"
  fi
}
