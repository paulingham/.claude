"""Sanitise CLAUDE_SESSION_ID for the tool-allowlist log entry.

Mirrors the bash-side sanitisation in log-allowlist.sh so the on-disk
log path and the json `session_id` field always agree, preserving
forensic correlation between file location and entries.
"""
import os
import re

_STRING_CAP = 64
_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_-]")
_ALL_UNDERSCORE_RE = re.compile(r"^_+$")


def sanitize_session(raw):
    sanitized = _SANITIZE_RE.sub("_", raw)
    if not sanitized or _ALL_UNDERSCORE_RE.match(sanitized):
        sanitized = f"local-{os.getpid()}"
    return sanitized[:_STRING_CAP]
