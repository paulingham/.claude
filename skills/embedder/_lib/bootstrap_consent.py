"""Consent gate for privileged installs (H1 security).

Commands whose first token is ``sudo`` must not execute without an
explicit user yes. Three bypass pathways:
  - TTY prompt accepts ``y``/``yes`` (case-insensitive)
  - ``CLAUDE_BOOTSTRAP_CONSENT=1`` skips the prompt
  - Non-TTY with env var unset aborts with a clear hint
"""
import os
import sys

_ENV_KEY = "CLAUDE_BOOTSTRAP_CONSENT"
_YES = {"y", "yes"}


def grants(cmd, warn):
    if not _needs_consent(cmd):
        return True
    if os.environ.get(_ENV_KEY) == "1":
        return True
    if not sys.stdin.isatty():
        warn(f"aborting: set {_ENV_KEY}=1 to run: {' '.join(cmd)}")
        return False
    return _prompt(cmd, warn)


def _needs_consent(cmd):
    return bool(cmd) and cmd[0] == "sudo"


def _prompt(cmd, warn):
    answer = input(f"About to run: {' '.join(cmd)}. Continue? [y/N] ")
    if answer.strip().lower() in _YES:
        return True
    warn("aborting: consent not granted")
    return False
