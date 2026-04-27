"""Shared validator for `subagent_type` strings.

A safe subagent_type is a short kebab-case identifier — no path traversal,
no embedded slashes. Used by both the allowlist resolver and the YAML loader
to ensure they refuse to dereference attacker-controlled paths.
"""
import re

_VALID_SUBAGENT = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def is_valid_subagent_type(value):
    return bool(value) and bool(_VALID_SUBAGENT.match(value))
