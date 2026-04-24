#!/usr/bin/env bash
# /internal-eval run-case: execute ONE case through the inner /pipeline under
# full isolation. Story 6 scaffolding; Story 7 wires real pipeline dispatch.
# Contract: skills/internal-eval/run/SKILL.md + ISOLATION.md.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/lib/status.sh"
# shellcheck disable=SC1091
source "$HERE/lib/isolation.sh"
# shellcheck disable=SC1091
source "$HERE/lib/harness-ref.sh"
# shellcheck disable=SC1091
source "$HERE/lib/scoring.sh"
# shellcheck disable=SC1091
source "$HERE/lib/timeout.sh"
# shellcheck disable=SC1091
source "$HERE/lib/args.sh"
# shellcheck disable=SC1091
source "$HERE/lib/result-emit.sh"
# shellcheck disable=SC1091
source "$HERE/lib/runner.sh"

main "$@"
