#!/usr/bin/env bats
# Specs for hooks/_lib/project-hash.sh — portable _md5_hash + _project_hash.
# Hermetic: tests stub PATH / command -v where needed; no real git remote required.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/project-hash.sh"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

# ---------- AC1.1 / AC1.2: stdin form digests ----------

@test "AC1.1 _md5_hash 'abc' returns 900150983cd24fb0d6963f7d28e17f72" {
  run bash -c "source '$LIB'; printf 'abc' | _md5_hash"
  [ "$status" -eq 0 ]
  [ "$output" = "900150983cd24fb0d6963f7d28e17f72" ]
}

@test "AC1.3 _md5_hash empty stdin returns canonical empty-input digest" {
  run bash -c "source '$LIB'; printf '' | _md5_hash"
  [ "$status" -eq 0 ]
  [ "$output" = "d41d8cd98f00b204e9800998ecf8427e" ]
}

@test "AC1.6a _md5_hash exits non-zero when neither md5sum nor openssl is available" {
  # Stub command -v to claim both tools are missing; restricted PATH.
  run bash -c "source '$LIB'; command() { if [ \"\$1\" = -v ]; then return 1; fi; builtin command \"\$@\"; }; PATH=/empty _md5_hash < /dev/null"
  [ "$status" -ne 0 ]
}

# ---------- _project_hash: default fallback ----------

@test "AC1.6b _project_hash --fallback 'local' echoes local when md5 tool missing" {
  # Stub command -v to make both md5sum and openssl 'missing' to _md5_hash.
  run bash -c "source '$LIB'; command() { if [ \"\$1\" = -v ]; then return 1; fi; builtin command \"\$@\"; }; PATH=/empty _project_hash --fallback 'local'"
  [ "$status" -eq 0 ]
  [ "$output" = "local" ]
}

# ---------- AC1.5: per-caller fallback preservation with git stub ----------

# Create a fake 'git' on PATH that fails for all subcommands (simulates non-repo).
_mk_failing_git_stub() {
  local dir="$1"
  mkdir -p "$dir"
  cat >"$dir/git" <<'EOF'
#!/usr/bin/env bash
# Stub: simulate git failing — e.g., invoked outside a repo.
exit 128
EOF
  chmod +x "$dir/git"
}

@test "AC1.5a _project_hash --fallback 'local' returns local when git remote fails" {
  _mk_failing_git_stub "$TMP_DIR/bin"
  export PATH="$TMP_DIR/bin:$PATH"
  run bash -c "source '$LIB'; _project_hash --fallback 'local'"
  [ "$status" -eq 0 ]
  [ "$output" = "local" ]
}

@test "AC1.5b _project_hash --fallback '' returns empty string when git remote fails" {
  _mk_failing_git_stub "$TMP_DIR/bin"
  export PATH="$TMP_DIR/bin:$PATH"
  run bash -c "source '$LIB'; _project_hash --fallback ''"
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}

@test "AC1.5c _project_hash --fallback with basename expression evaluates in caller scope" {
  _mk_failing_git_stub "$TMP_DIR/bin"
  mkdir -p "$TMP_DIR/mocked-project"
  export PATH="$TMP_DIR/bin:$PATH"
  run bash -c "cd '$TMP_DIR/mocked-project' && source '$LIB'; _project_hash --fallback \"\$(basename \"\$(git rev-parse --show-toplevel 2>/dev/null || pwd)\")\""
  [ "$status" -eq 0 ]
  [ "$output" = "mocked-project" ]
}

@test "AC1.5d default fallback (no --fallback flag) is 'local'" {
  _mk_failing_git_stub "$TMP_DIR/bin"
  export PATH="$TMP_DIR/bin:$PATH"
  run bash -c "source '$LIB'; _project_hash"
  [ "$status" -eq 0 ]
  [ "$output" = "local" ]
}

# ---------- AC1.4: per-caller fallback preservation (grep assertions) ----------

@test "AC1.4a session-start-bootstrap.sh uses _project_hash --fallback \"local\"" {
  grep -q '_project_hash --fallback "local"' "$REPO_ROOT/hooks/session-start-bootstrap.sh"
}

@test "AC1.4a2 session-start-bootstrap.sh no longer uses openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/hooks/session-start-bootstrap.sh"
  [ "$output" = "0" ]
}

@test "AC1.4b cost-tracker.sh uses _project_hash --fallback \"\"" {
  grep -q '_project_hash --fallback ""' "$REPO_ROOT/hooks/cost-tracker.sh"
}

@test "AC1.4b2 cost-tracker.sh no longer uses openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/hooks/cost-tracker.sh"
  [ "$output" = "0" ]
}

@test "AC1.4c observation-capture.sh uses _project_hash with basename fallback" {
  grep -q '_project_hash --fallback "\$(basename "\$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"' "$REPO_ROOT/hooks/observation-capture.sh"
}

@test "AC1.4c2 observation-capture.sh no longer uses openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/hooks/observation-capture.sh"
  [ "$output" = "0" ]
}

@test "AC1.4d test-hooks.sh uses _project_hash basename fallback (2 sites)" {
  # Expect two occurrences of the basename-fallback call site
  count=$(grep -c '_project_hash --fallback "\$(basename "\$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"' "$REPO_ROOT/hooks/tests/test-hooks.sh" || true)
  [ "$count" = "2" ]
}

@test "AC1.4d2 test-hooks.sh no longer uses openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/hooks/tests/test-hooks.sh"
  [ "$output" = "0" ]
}

@test "AC1.4e auto-bug-detect.sh calls _md5_hash directly (no _project_hash/--fallback)" {
  grep -q '| _md5_hash' "$REPO_ROOT/hooks/auto-bug-detect.sh"
  ! grep -q '_project_hash' "$REPO_ROOT/hooks/auto-bug-detect.sh"
  ! grep -q -- '--fallback' "$REPO_ROOT/hooks/auto-bug-detect.sh"
}

@test "AC1.4e2 auto-bug-detect.sh no longer uses openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/hooks/auto-bug-detect.sh"
  [ "$output" = "0" ]
}

# ---------- AC1.4 docs: rewrite openssl md5 -r references ----------

@test "AC1.4f rules/autonomous-intelligence.md no openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/rules/autonomous-intelligence.md"
  [ "$output" = "0" ]
}

@test "AC1.4g orchestrator/agent-orchestration.md no openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/orchestrator/agent-orchestration.md"
  [ "$output" = "0" ]
}

@test "AC1.4h skills/learn/SKILL.md no openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/skills/learn/SKILL.md"
  [ "$output" = "0" ]
}

@test "AC1.4i skills/batch-pipeline/SKILL.md no openssl md5 -r" {
  run grep -c "openssl md5 -r" "$REPO_ROOT/skills/batch-pipeline/SKILL.md"
  [ "$output" = "0" ]
}

@test "AC1.5e _project_hash returns md5 digest when git remote succeeds" {
  mkdir -p "$TMP_DIR/bin"
  cat >"$TMP_DIR/bin/git" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "remote" && "$2" == "get-url" && "$3" == "origin" ]]; then
  printf 'https://example.com/repo.git'
  exit 0
fi
exit 0
EOF
  chmod +x "$TMP_DIR/bin/git"
  expected="bc6fa1f09b2a9f7a7bdfb9a3b91eeaaa"  # md5(https://example.com/repo.git) — verify live
  expected=$(printf 'https://example.com/repo.git' | md5sum 2>/dev/null | awk '{print $1}')
  if [[ -z "$expected" ]]; then
    expected=$(printf 'https://example.com/repo.git' | openssl dgst -md5 | awk '{print $NF}')
  fi
  export PATH="$TMP_DIR/bin:$PATH"
  run bash -c "source '$LIB'; _project_hash --fallback 'local'"
  [ "$status" -eq 0 ]
  [ "$output" = "$expected" ]
}
