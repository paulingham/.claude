#!/usr/bin/env bash
# Wave 4-L bats helpers shared by parity + e2e tests.
# Requires: REPO_ROOT, FIXTURE, WORK, PR, CLAUDE_GH_CACHE_DIR, CLAUDE_SESSION_ID.

w4l_install_fail_gh() {
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<'SH'
#!/usr/bin/env bash
echo "MOCK GH SHOULD NOT BE INVOKED ON CACHE HIT" >&2
exit 99
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"
}

w4l_install_mock_gh_with_fixture() {
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<SH
#!/usr/bin/env bash
sub="\$2"
case "\$sub" in
  view) cat "$FIXTURE/view.json" ;;
  diff)
    for a in "\$@"; do [ "\$a" = "--name-only" ] && { cat "$FIXTURE/files.txt"; exit 0; }; done
    cat "$FIXTURE/diff.patch" ;;
esac
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"
}

w4l_seed_cache() {
  local cd="$CLAUDE_GH_CACHE_DIR/$CLAUDE_SESSION_ID-$PR"
  mkdir -p "$cd"
  cp "$FIXTURE/view.json"  "$cd/view.json"
  cp "$FIXTURE/diff.patch" "$cd/diff.patch"
  cp "$FIXTURE/files.txt"  "$cd/files.txt"
  : > "$cd/.complete"
}
