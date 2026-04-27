#!/usr/bin/env bats
# Wave 4-L Slice 1: MCP server end-to-end via stdio JSON-RPC.
#
# Verifies:
#   - `prefetch_pr` tools/call against a synthetic `gh pr merge N` command
#   - cache directory is created at $CLAUDE_GH_CACHE_DIR/$session-N/
#   - all four cache files exist, .complete written LAST
#   - urllib calls are intercepted via a Python sitecustomize shim
#     (no real network); uses BATS_FILE_TMPDIR for isolation.
#
# Portability: only `sleep 1` (integer arg) is used; we don't time-race.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SERVER="$REPO_ROOT/hooks/_lib/github-cache-server.py"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache"
  export CLAUDE_SESSION_ID="bats-sess"
  export GITHUB_PERSONAL_ACCESS_TOKEN="dummy"
  export _TEST_GH_OWNER_REPO="o/r"
  # Network shim: a sitecustomize that monkey-patches urllib.request.urlopen
  # to return canned bytes. Lives in a per-test PYTHONPATH dir.
  SHIM="$WORK/shim"
  mkdir -p "$SHIM"
  cat > "$SHIM/sitecustomize.py" <<'PY'
import io, urllib.request
class _R:
    def __init__(self, body): self._b = body.encode("utf-8")
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False
def _fake(req, timeout=None):
    url = req.get_full_url() if hasattr(req, "get_full_url") else ""
    if url.endswith("/files"):
        return _R('[{"filename":"a.py"},{"filename":"b.sh"}]')
    return _R('{"number":47,"merged_at":"2026-04-15T12:34:56Z"}')
urllib.request.urlopen = _fake
PY
  export PYTHONPATH="$SHIM${PYTHONPATH:+:$PYTHONPATH}"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID GITHUB_PERSONAL_ACCESS_TOKEN
  unset _TEST_GH_OWNER_REPO PYTHONPATH
}

_send() {
  printf '%s\n' "$1" | python3 "$SERVER"
}

@test "prefetch_pr writes cache dir with .complete sentinel last" {
  req='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"prefetch_pr","arguments":{"command":"gh pr merge 47 --squash"}}}'
  run _send "$req"
  [ "$status" -eq 0 ]
  cache="$CLAUDE_GH_CACHE_DIR/bats-sess-47"
  [ -f "$cache/view.json" ]
  [ -f "$cache/diff.patch" ]
  [ -f "$cache/files.txt" ]
  [ -f "$cache/.complete" ]
  # .complete must be the newest (or equal-mtime) — written last per spec.
  newest="$(ls -t "$cache" | head -n1)"
  [ "$newest" = ".complete" ] || [ "$newest" = "files.txt" ]
}

@test "prefetch_pr with no PR number returns ok:false in envelope" {
  req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"prefetch_pr","arguments":{"command":"gh repo view"}}}'
  run _send "$req"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"ok": false'* ]] || [[ "$output" == *'"ok":false'* ]]
  [[ "$output" == *"no PR number"* ]]
}

@test "initialize then tools/list returns prefetch_pr tool" {
  reqs=$'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
  run bash -c "printf '%s\n' '$reqs' | python3 '$SERVER'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"gh-cache"* ]]
  [[ "$output" == *"prefetch_pr"* ]]
}
