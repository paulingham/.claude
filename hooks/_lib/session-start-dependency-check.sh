#!/usr/bin/env bash
# SessionStart dependency warner — sourced by session-start-bootstrap.sh.
# Sources the probe lib, prints STDERR warnings. ALWAYS returns 0 (never blocks).
# WHY: SessionStart cannot block (the hook has no enforcing mechanism); the
#      PreToolUse:Agent gate (harness-dependency-gate.sh) is the enforcing layer.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-dependency-check.sh" 2>/dev/null || return 0

_ssdc_check_deps() {
  _hdc_probe 2>/dev/null || true

  if [ -n "${HDC_MISSING:-}" ]; then
    printf '[harness-dependency-check] MISSING REQUIRED: %s — install Git for Windows AND a Python interpreter, then add "env":{"CLAUDE_CODE_GIT_BASH_PATH":"C:\\Program Files\\Git\\bin\\bash.exe"} to settings.json. See knowledge/windows-setup.md.\n' \
      "$HDC_MISSING" >&2
  fi

  if [ -n "${HDC_SOFT_MISSING:-}" ]; then
    printf '[harness-dependency-check] OPTIONAL not found: flock (advisory — concurrency locking degrades gracefully; not required to run pipelines).\n' >&2
  fi

  return 0
}
