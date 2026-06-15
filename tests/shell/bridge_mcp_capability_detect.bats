#!/usr/bin/env bats
# CI bridge for hooks/tests/test-mcp-capability-detect.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-mcp-capability-detect harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-mcp-capability-detect.sh"; [ "$status" -eq 0 ]; }
@test "test-mcp-capability-detect reports 10 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-mcp-capability-detect.sh"; echo "$output" | grep -q "10 passed, 0 failed"; }
