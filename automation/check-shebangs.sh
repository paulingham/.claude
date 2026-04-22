#!/usr/bin/env bash
# Fails if any tracked *.sh file uses `#!/bin/bash` instead of
# `#!/usr/bin/env bash`. The portable form works on macOS, Ubuntu, Alpine,
# NixOS, and any other distro that ships bash anywhere on PATH.
# Guard for the cross-env-portability H2 finding.
# See tests/shell/shebang-uniformity.bats.
set -euo pipefail

# shellcheck disable=SC2016  # literal shebang strings below, not expansions
_report_offenders() {
  printf 'error: non-portable shebang `#!/bin/bash` found in:\n%s\n' "$1" >&2
  printf 'fix: replace with `#!/usr/bin/env bash` (portable on macOS/Alpine/NixOS).\n' >&2
}

main() {
  local offenders
  offenders=$(git ls-files '*.sh' | xargs grep -l '^#!/bin/bash' 2>/dev/null || true)
  [[ -z "$offenders" ]] && return 0
  _report_offenders "$offenders"
  return 1
}

main "$@"
