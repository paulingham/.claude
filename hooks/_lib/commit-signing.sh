#!/usr/bin/env bash
# commit-signing.sh — commit-signing config resolver + reachability gate.
#
# Sourced (not executed). Provides _cs_* helpers that read a git scope's
# signing configuration and verify the signing material is actually usable
# before an agent produces commits a remote (GitHub Enterprise) will reject.
#
# WHY this exists: every harness agent commits inside a git worktree created
# by worktree-create.sh. Worktrees inherit the parent repo's local config and
# the user's global git config, so commit signing propagates AUTOMATICALLY
# when commit.gpgsign=true + a valid user.signingkey are set. Nothing here
# turns signing ON or picks a key — that is the user's job (register the key
# in GHE first, then set git config). These helpers only verify propagation.
#
# WHY no `set` flags: this file is sourced into callers (e.g. worktree-create.sh
# runs under `set -euo pipefail`). Each function returns its own status so the
# caller can branch with `if ! _cs_... ; then` and not trip the caller's set -e.

# Echoes the resolved commit.gpgsign bool for <dir>'s git scope (empty if unset).
_cs_signing_enabled() {
  git -C "${1:-.}" config --get --type=bool commit.gpgsign 2>/dev/null
}

# Echoes gpg.format for <dir> (defaults to openpgp, git's own default).
_cs_format() {
  git -C "${1:-.}" config --get gpg.format 2>/dev/null || echo openpgp
}

# Echoes user.signingkey for <dir> (may be empty).
_cs_signing_key() {
  git -C "${1:-.}" config --get user.signingkey 2>/dev/null
}

# Fail-closed reachability gate (Iron Law 8 style).
#   return 0 — signing is OFF (nothing to guarantee), OR signing is ON and the
#              signing material is reachable.
#   return 1 — signing is ON but the key/material is missing/unreadable; a
#              human-readable reason is echoed to stdout.
#
# WHY fail-closed here means "return 1 + reason", NOT "block": a worktree with
# broken signing is recoverable (the user fixes their git config and re-commits),
# whereas refusing to create the worktree halts all work. The caller surfaces
# the reason as a non-blocking warning. The gate still refuses to silently
# pass when it cannot prove the signing material is usable.
_cs_verify_reachable() {
  local dir="${1:-.}"
  local enabled
  enabled=$(_cs_signing_enabled "$dir")
  [[ "$enabled" == "true" ]] || return 0

  local key
  key=$(_cs_signing_key "$dir")
  if [[ -z "$key" ]]; then
    echo "commit.gpgsign=true but user.signingkey is unset"
    return 1
  fi

  local format
  format=$(_cs_format "$dir")
  case "$format" in
    ssh)
      _cs_verify_ssh_key "$key"
      ;;
    *)
      _cs_verify_gpg_key "$key"
      ;;
  esac
}

# SSH signing: the key is a path to a private/public key file, OR the literal
# inline form `key::<material>` which carries the material directly.
_cs_verify_ssh_key() {
  local key="$1"
  [[ "$key" == key::* ]] && return 0

  local resolved="${key/#\~/$HOME}"
  if [[ ! -r "$resolved" ]]; then
    echo "gpg.format=ssh but signing key file is unreadable: $resolved"
    return 1
  fi
  return 0
}

# openpgp/gpg signing: the key must resolve to a present secret key.
_cs_verify_gpg_key() {
  local key="$1"
  if ! gpg --list-secret-keys "$key" >/dev/null 2>&1; then
    echo "gpg secret key not found for user.signingkey: $key"
    return 1
  fi
  return 0
}
