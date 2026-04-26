#!/usr/bin/env bash
# Human-readable regression.md renderer — consumed by PR body stamping (Story 9).

_rmd_dir="$(dirname "${BASH_SOURCE[0]}")"

# render_regression_md <regression.json> → stdout markdown
render_regression_md() {
  jq -r -f "$_rmd_dir/regression-md.jq" "$1"
}
