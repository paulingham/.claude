"""Env-var resolution for instinct_injector (Wave 4-M Slice 1).

CLAUDE_INSTINCT_MIN_CONFIDENCE -> float (default 0.4; invalid -> default + warn)
CLAUDE_INSTINCT_TOP_N          -> int   (default 5;   invalid/neg -> default)
"""
import os
import sys


def resolve_min_confidence(default):
    raw = os.environ.get("CLAUDE_INSTINCT_MIN_CONFIDENCE")
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        sys.stderr.write(f"[instinct_injector] invalid MIN_CONFIDENCE={raw!r}; using {default}\n")
        return default


def resolve_top_n(default):
    raw = os.environ.get("CLAUDE_INSTINCT_TOP_N")
    if raw is None:
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return n if n >= 0 else default
