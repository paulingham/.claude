#!/usr/bin/env bats
# H2: End-to-end parity test exercising the REAL server-write path against
# REAL REST API bytes (urllib monkey-patched), then the REAL consumer-read
# path. No fixture-seeded shortcut. Asserts the server reshapes REST →
# gh-CLI shape (C1+C2) and consumers see byte-identical output regardless
# of which path produced the cache.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SERVER="$REPO_ROOT/hooks/_lib/github-cache-server.py"
  REST="$REPO_ROOT/tests/fixtures/wave4l/rest-fixture"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache"
  export CLAUDE_SESSION_ID="bats-h2"
  export GITHUB_PERSONAL_ACCESS_TOKEN="dummy"
  export _TEST_GH_OWNER_REPO="o/r"

  SHIM="$WORK/shim"
  mkdir -p "$SHIM"
  cat > "$SHIM/sitecustomize.py" <<PY
import urllib.request
class _R:
    def __init__(self, body): self._b = body.encode("utf-8")
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False
def _fake(req, timeout=None):
    url = req.get_full_url() if hasattr(req, "get_full_url") else ""
    if url.endswith("/files"):
        return _R(open("$REST/files-rest.json").read())
    if "Accept" in (req.headers if hasattr(req, "headers") else {}):
        accept = req.headers.get("Accept", "")
    else:
        accept = ""
    if "diff" in accept:
        return _R(open("$REST/diff.patch").read())
    return _R(open("$REST/view-rest.json").read())
urllib.request.urlopen = _fake
PY
  export PYTHONPATH="$SHIM${PYTHONPATH:+:$PYTHONPATH}"
  PR=1234
  CACHE_DIR="$CLAUDE_GH_CACHE_DIR/bats-h2-$PR"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID GITHUB_PERSONAL_ACCESS_TOKEN
  unset _TEST_GH_OWNER_REPO PYTHONPATH
}

_prefetch() {
  local req='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"prefetch_pr","arguments":{"command":"gh pr merge '"$PR"' --squash"}}}'
  printf '%s\n' "$req" | python3 "$SERVER"
}

@test "H2: server-write from REST fixture creates complete cache" {
  run _prefetch
  [ "$status" -eq 0 ]
  [ -f "$CACHE_DIR/view.json" ]
  [ -f "$CACHE_DIR/diff.patch" ]
  [ -f "$CACHE_DIR/files.txt" ]
  [ -f "$CACHE_DIR/.complete" ]
}

@test "H2: server reshapes REST merged_at -> gh-shape mergedAt (C1)" {
  _prefetch
  view="$(cat "$CACHE_DIR/view.json")"
  [[ "$view" == *'"mergedAt"'* ]]
  [[ "$view" != *'"merged_at"'* ]]
  [[ "$view" == *'"2026-04-15T12:34:56Z"'* ]]
}

@test "H2: server reshapes merge_commit_sha -> mergeCommit.oid (C1)" {
  _prefetch
  view="$(cat "$CACHE_DIR/view.json")"
  [[ "$view" == *'"mergeCommit"'* ]]
  [[ "$view" == *'"oid"'* ]]
  [[ "$view" == *'"deadbeef0000000000000000000000000000abcd"'* ]]
  [[ "$view" != *'"merge_commit_sha"'* ]]
}

@test "H2: server prunes label objects to {name:...} (C1)" {
  _prefetch
  view="$(cat "$CACHE_DIR/view.json")"
  [[ "$view" == *'"labels"'* ]]
  [[ "$view" == *'"name":"bug"'* ]]
  [[ "$view" != *'"color"'* ]]
  [[ "$view" != *'"description"'* ]]
}

@test "H2: server reshapes /files REST array -> newline-delimited (C2)" {
  _prefetch
  files="$(cat "$CACHE_DIR/files.txt")"
  [[ "$files" == *"tests/test_flaky_thing.py"* ]]
  [[ "$files" == *"hooks/_lib/something.sh"* ]]
  [[ "$files" != *'['* ]]
  [[ "$files" != *'{'* ]]
}

@test "H2: consumer ecw_fetch_view reads cache and gets gh-shape (no gh call)" {
  _prefetch
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<'SH'
#!/usr/bin/env bash
echo "GH MUST NOT BE CALLED ON REST E2E" >&2
exit 99
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  view="$(ecw_fetch_view "$PR")"
  [ -n "$view" ]
  [[ "$view" == *'"mergedAt":"2026-04-15T12:34:56Z"'* ]]
  [[ "$view" == *'"mergeCommit"'* ]]
}

@test "H2: consumer ecw_fetch_names reads files.txt produced from REST array" {
  _prefetch
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<'SH'
#!/usr/bin/env bash
echo "GH MUST NOT BE CALLED" >&2; exit 99
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  names="$(ecw_fetch_names "$PR")"
  [[ "$names" == *"tests/test_flaky_thing.py"* ]]
  [[ "$names" == *"hooks/_lib/something.sh"* ]]
}

@test "H2: pr_view_from_cache (case-build path) hits REST-built cache" {
  _prefetch
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  view="$(pr_view_from_cache "$PR")"
  [[ "$view" == *'"mergedAt"'* ]]
}
