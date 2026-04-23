#!/usr/bin/env bash
# Extension point for external (non-Anthropic) /best-of-n candidates.
#
# A real implementation would:
#   1. Read slice spec from --slice-spec-path
#   2. Call the provider SDK (OpenAI, Google, etc) with the slice spec
#   3. Write produced files into the candidate's worktree (cwd)
#   4. Commit to --branch
#   5. Print the commit SHA on stdout
#
# Current behaviour: honest stub. Returns non-zero with a clear stderr message.
# /best-of-n SKILL.md treats non-zero exit as "skip this candidate" — never fabricate results.
set -euo pipefail

SLUG="" ; TASK_ID="" ; SLICE="" ; BRANCH="" ; REQ_ENV=""

while [ $# -gt 0 ]; do
  case "$1" in
    --candidate-slug) SLUG="$2" ; shift 2 ;;
    --task-id) TASK_ID="$2" ; shift 2 ;;
    --slice-spec-path) SLICE="$2" ; shift 2 ;;
    --branch) BRANCH="$2" ; shift 2 ;;
    --required-env) REQ_ENV="$2" ; shift 2 ;;
    *) echo "external-runner: unknown arg: $1" >&2 ; exit 2 ;;
  esac
done

if [ -n "$REQ_ENV" ] && [ -z "${!REQ_ENV:-}" ]; then
  echo "external-runner: required env var ${REQ_ENV} not set; skipping candidate=${SLUG}" >&2
  exit 1
fi

echo "external-runner: not yet implemented for candidate=${SLUG} (task=${TASK_ID} branch=${BRANCH} slice=${SLICE}); skipping" >&2
exit 1
