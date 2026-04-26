#!/usr/bin/env bash
# /internal-eval run-suite: orchestrates N cases via run-case.sh with
# concurrency, resumability, and aggregation. Contract: run/SKILL.md.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/lib/suite-args.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-resume.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-aggregate.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-harness.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-pool.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-enumerate.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-state.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-dispatch.sh"
# shellcheck disable=SC1091
source "$HERE/lib/suite-main.sh"

suite_main "$@"
