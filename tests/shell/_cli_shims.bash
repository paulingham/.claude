#!/usr/bin/env bash
# Shared CLI shims for session-store bats tests. Source from setup().
# Each installer writes shim binaries to $BIN_DIR (default: $BATS_TMPDIR/bin)
# and prepends that directory to PATH. To isolate test files from each other,
# setup() should set BIN_DIR to a per-file tmpdir (see session_store_*.bats).

install_aws_shim() {
  : "${BIN_DIR:=$BATS_TMPDIR/bin}"
  mkdir -p "$BIN_DIR"
  rm -f "$BIN_DIR/aws"
  cat > "$BIN_DIR/aws" <<'AWS_SHIM'
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
  chmod +x "$BIN_DIR/aws"
  export PATH="$BIN_DIR:$PATH"
}

install_redis_shim() {
  : "${BIN_DIR:=$BATS_TMPDIR/bin}"
  mkdir -p "$BIN_DIR"
  rm -f "$BIN_DIR/redis-cli"
  cat > "$BIN_DIR/redis-cli" <<'REDIS_SHIM'
#!/usr/bin/env bash
echo "$@" >> "$REDIS_LOG"
args=("$@"); cmd=""; key=""
for ((i=0; i<${#args[@]}; i++)); do
  case "${args[$i]}" in
    -u) i=$((i+1)) ;;
    -x) ;;
    SET|GET|DEL|KEYS|EXISTS) cmd="${args[$i]}"; key="${args[$((i+1))]}"; break ;;
  esac
done
key_file_for() { printf '%s' "$REDIS_FAKE_STORE/$(echo -n "$1" | md5sum 2>/dev/null | awk '{print $1}' || echo -n "$1" | openssl dgst -md5 | awk '{print $NF}')"; }
register_key() { grep -qxF "$1" "$REDIS_FAKE_STORE/.keys" 2>/dev/null || echo "$1" >> "$REDIS_FAKE_STORE/.keys"; }
unregister_key() { local tmp; tmp=$(mktemp); grep -vxF "$1" "$REDIS_FAKE_STORE/.keys" > "$tmp" 2>/dev/null; mv "$tmp" "$REDIS_FAKE_STORE/.keys"; }
file=$(key_file_for "$key")
case "$cmd" in
  SET) cat > "$file"; register_key "$key"; echo OK ;;
  GET) [[ -f "$file" ]] && cat "$file" || { echo ""; exit 0; } ;;
  EXISTS) [[ -f "$file" ]] && echo 1 || echo 0 ;;
  DEL) rm -f "$file"; unregister_key "$key"; echo 1 ;;
  KEYS)
    pattern="${key//\*/}"
    [[ -f "$REDIS_FAKE_STORE/.keys" ]] || exit 0
    while read -r k; do case "$k" in "$pattern"*) echo "$k" ;; esac; done < "$REDIS_FAKE_STORE/.keys" ;;
  *) exit 1 ;;
esac
REDIS_SHIM
  chmod +x "$BIN_DIR/redis-cli"
  export PATH="$BIN_DIR:$PATH"
}

install_aws_shim_404() {
  : "${BIN_DIR:=$BATS_TMPDIR/bin}"
  : "${AWS_LOG:=$BATS_TMPDIR/aws.log}"
  export AWS_LOG; : > "$AWS_LOG"
  mkdir -p "$BIN_DIR"; rm -f "$BIN_DIR/aws"
  cat > "$BIN_DIR/aws" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
exit 1
SHIM
  chmod +x "$BIN_DIR/aws"
  export PATH="$BIN_DIR:$PATH"
}

install_aws_shim_with_blob() {
  : "${BIN_DIR:=$BATS_TMPDIR/bin}"
  : "${AWS_LOG:=$BATS_TMPDIR/aws.log}"
  export AWS_LOG; : > "$AWS_LOG"; export AWS_BLOB="$1"
  mkdir -p "$BIN_DIR"; rm -f "$BIN_DIR/aws"
  cat > "$BIN_DIR/aws" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
case "$1 $2" in
  "s3 cp")
    if [[ "$3" == s3://* ]]; then printf '%b' "$AWS_BLOB"; exit 0; fi
    cat > /dev/null; exit 0 ;;
esac
exit 1
SHIM
  chmod +x "$BIN_DIR/aws"
  export PATH="$BIN_DIR:$PATH"
}

install_aws_shim_record() {
  : "${BIN_DIR:=$BATS_TMPDIR/bin}"
  : "${AWS_LOG:=$BATS_TMPDIR/aws.log}"
  export AWS_LOG; : > "$AWS_LOG"
  mkdir -p "$BIN_DIR"; rm -f "$BIN_DIR/aws"
  cat > "$BIN_DIR/aws" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
[[ "$1 $2" == "s3 cp" ]] && exit 0
exit 1
SHIM
  chmod +x "$BIN_DIR/aws"
  export PATH="$BIN_DIR:$PATH"
}
