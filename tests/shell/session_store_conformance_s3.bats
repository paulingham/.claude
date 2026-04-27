#!/usr/bin/env bats
# Conformance suite — S3 backend driver. Uses on-disk aws shim.

setup() {
  export HOME="$(mktemp -d)"
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="conf-bucket"
  export CLAUDE_SESSION_STORE_PREFIX="sessions/"
  export AWS_LOG="$BATS_TMPDIR/aws-cnf.log"; : > "$AWS_LOG"
  export AWS_FAKE_STORE="$BATS_TMPDIR/aws-cnf-store"; mkdir -p "$AWS_FAKE_STORE"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_aws_shim
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  source "$BATS_TEST_DIRNAME/_conformance_cases.bash"
}

install_aws_shim() {
  mkdir -p "$BATS_TMPDIR/bin"
  cat > "$BATS_TMPDIR/bin/aws" <<'AWS_SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
key_path() { local uri="$1"; echo "$AWS_FAKE_STORE/${uri#s3://}"; }
case "$1 $2" in
  "s3 cp")
    src="$3"; dst="$4"
    if [[ "$src" == s3://* ]]; then
      f=$(key_path "$src"); [[ -f "$f" ]] || exit 1
      [[ "$dst" = "-" ]] && cat "$f" || cp "$f" "$dst"
    else
      f=$(key_path "$dst"); mkdir -p "$(dirname "$f")"
      [[ "$src" = "-" ]] && cat > "$f" || cp "$src" "$f"
    fi ;;
  "s3 ls")
    uri="$3"; root=$(key_path "$uri")
    [[ -d "$root" ]] || exit 0
    ( cd "$root" && find . -maxdepth 1 -mindepth 1 -type d | sed 's|^\./||; s|$|/|; s|^|PRE |' ) ;;
  "s3 rm")
    f=$(key_path "$3"); rm -f "$f" ;;
  *) exit 1 ;;
esac
AWS_SHIM
  chmod +x "$BATS_TMPDIR/bin/aws"
  export PATH="$BATS_TMPDIR/bin:$PATH"
}

teardown() { rm -rf "$HOME"; rm -rf "$AWS_FAKE_STORE"; rm -f "$BATS_TMPDIR/bin/aws"; }

@test "conformance/s3: round-trip" { assert_round_trip; }
@test "conformance/s3: get miss → exit 1" { assert_get_miss_exit_1; }
@test "conformance/s3: delete then get → miss" { assert_delete_then_get_miss; }
@test "conformance/s3: list includes hash" { assert_list_includes_hash; }
@test "conformance/s3: list_subkeys emits headers" { assert_list_subkeys_emits_headers; }
@test "conformance/s3: put dash reads stdin" { assert_put_dash_reads_stdin; }
@test "conformance/s3: section headers survive round-trip" { assert_section_headers_survive_round_trip; }
