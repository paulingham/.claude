#!/usr/bin/env bash
# Fails if any tracked file uses `#!/bin/bash` instead of `#!/usr/bin/env bash`.
# The portable form works on macOS, Ubuntu, Alpine, NixOS, and any other distro
# that ships bash anywhere on PATH. Guards the cross-env-portability H2 finding.
# Selection is shebang-based (not extension-based) so it catches .sh, .bash,
# and extensionless executables uniformly. See tests/shell/shebang-uniformity.bats.
set -euo pipefail

# shellcheck disable=SC2016  # literal shebang strings below, not expansions
_report_offenders() {
  printf 'error: non-portable shebang `#!/bin/bash` found in:\n%s\n' "$1" >&2
  printf 'fix: replace with `#!/usr/bin/env bash` (portable on macOS/Alpine/NixOS).\n' >&2
}

_find_offenders() {
  # NUL-delimited file list → NUL-safe grep. `-r` avoids hang if list empty.
  git ls-files -z | xargs -0 -r grep -l '^#!/bin/bash' 2>/dev/null || true
}

main() {
  local offenders
  offenders=$(_find_offenders)
  [[ -z "$offenders" ]] && return 0
  _report_offenders "$offenders"
  return 1
}

main "$@"
