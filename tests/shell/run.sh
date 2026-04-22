#!/usr/bin/env bash
# Wrapper around bats-core: SKIPs cleanly when bats is absent so the test
# suite remains green on machines that have not yet run the installer.
# Pass --require-bats in CI to turn the SKIP into a hard failure.
# Portable to bash 3.2 (macOS default) — no mapfile, no readarray.
set -euo pipefail

require_bats=0
[[ "${1:-}" == "--require-bats" ]] && require_bats=1

if ! command -v bats >/dev/null 2>&1; then
  echo "SKIP: bats-core not installed"
  exit "$require_bats"
fi

shell_dir="$(cd "$(dirname "$0")" && pwd)"
specs=$(find "$shell_dir" -type f -name '*.bats' | sort)
[[ -z "$specs" ]] && { echo "no .bats specs found under $shell_dir"; exit 0; }
# shellcheck disable=SC2086
exec bats $specs
