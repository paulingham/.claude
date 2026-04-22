#!/usr/bin/env bash
# Portable MD5 + project-hash helpers for hooks.
# Source this file; call _md5_hash or _project_hash.

_md5_tool() {
  command -v md5sum >/dev/null 2>&1 && { echo md5sum; return 0; }
  command -v openssl >/dev/null 2>&1 && { echo openssl; return 0; }
  return 1
}

_md5_hash() {
  local tool; tool=$(_md5_tool) || return 1
  [[ "$tool" == "md5sum" ]] && { md5sum | awk '{print $1}'; return; }
  openssl dgst -md5 | awk '{print $NF}'
}

_project_hash_fallback() {
  [[ "${1:-}" == "--fallback" ]] && { echo "$2"; return; }
  echo "local"
}

_project_hash() {
  local fallback; fallback=$(_project_hash_fallback "$@")
  local url; url=$(git remote get-url origin 2>/dev/null) || { echo "$fallback"; return; }
  [[ -z "$url" ]] && { echo "$fallback"; return; }
  printf '%s' "$url" | _md5_hash || echo "$fallback"
}
