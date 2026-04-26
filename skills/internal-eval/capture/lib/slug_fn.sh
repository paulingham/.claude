#!/usr/bin/env bash
# Sourceable slugify function — same logic as slug.sh.
slugify() {
  local s="$1"
  s="$(printf '%s' "$s" | LC_ALL=C tr '[:upper:]' '[:lower:]' \
       | LC_ALL=C sed 's/[^a-z0-9]/-/g; s/-\{2,\}/-/g; s/^-*//; s/-*$//')"
  printf '%s' "$s"
}
