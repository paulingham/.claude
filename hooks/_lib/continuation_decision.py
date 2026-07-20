#!/usr/bin/env python3
"""Pure discriminator for the auto-continue protocol (advisory, unregistered).

Maps a `build_result_reader.py` status plus worktree commit presence onto
one of DONE/CONTINUE/WAIT/RECOVER for the orchestrator to act on. This is
NOT a hook and is NEVER registered — idle-mid-run is invisible to the
harness (the only subagent lifecycle hook is SubagentStop, which fires on
stop only), so this function is consumed by the orchestrator LLM as plain
advisory logic, not wired into any PreToolUse/PostToolUse/Stop matcher.

SAFETY: a legitimately-working agent is unobservable (no reader write yet,
no commits yet) and must never be poked or double-dispatched into a live
worktree. Any input this function cannot classify with confidence returns
WAIT, never DONE or CONTINUE (Iron Law 8 — fail closed).
"""
from __future__ import annotations

RECOVERABLE_STATUSES = {"MISSING", "CORRUPT"}
TERMINAL_DECISIONS = {"COMPLETE": "DONE", "FAILED": "RECOVER"}


def _recoverable_decision(commits_present):
    return "CONTINUE" if commits_present else "RECOVER"


# Returns DONE|CONTINUE|WAIT|RECOVER; unknown/empty/garbage input -> WAIT.
def continuation_decision(reader_status, commits_present):
    if reader_status in TERMINAL_DECISIONS:
        return TERMINAL_DECISIONS[reader_status]
    if reader_status in RECOVERABLE_STATUSES:
        return _recoverable_decision(commits_present)
    return "WAIT"


if __name__ == "__main__":
    import sys

    status_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    commits_arg = sys.argv[2] if len(sys.argv) > 2 else ""
    print(continuation_decision(status_arg, commits_arg == "true"))
