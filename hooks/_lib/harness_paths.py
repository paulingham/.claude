"""Canonical Python path resolver — mirrors harness-paths.sh contract.

Three-tier resolution (matches hooks/_lib/harness-paths.sh:13-14):
  harness_data(): CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > Path.home()/".claude"
  harness_root(): CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > Path.home()/".claude"

Used by all hooks/_lib/*.py callers that previously hardcoded Path.home()/".claude".
Skills processes must use the sibling resolver module (independent sys.path).
"""
import os
from pathlib import Path

_SHELL_METACHARS = frozenset('"$`;\n|&<>()')


def _validate_base(p: Path) -> Path:
    """Validate a resolved base path; raise ValueError on unsafe values."""
    s = str(p)
    if not s.startswith("/"):
        raise ValueError(f"harness_paths: path must be absolute, got: {s!r}")
    if ".." in Path(s).parts:
        raise ValueError(f"harness_paths: path must not contain '..', got: {s!r}")
    if any(c in s for c in _SHELL_METACHARS):
        raise ValueError(f"harness_paths: path contains shell metachar, got: {s!r}")
    return p


def _resolved_harness_data() -> str:
    """HARNESS_DATA env > harness_data() fallback; shared helper for callers."""
    return os.environ.get("HARNESS_DATA") or str(harness_data())


def resolved_harness_data() -> str:
    """Documented helper: HARNESS_DATA env > harness_data() resolver fallback.

    Use this instead of repeating the inline pattern at every call site.
    Five callers in hooks/_lib use this to locate the metrics/pipeline-state tree.
    """
    return _resolved_harness_data()


def harness_data() -> Path:
    """Runtime-state base dir: CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > ~/.claude."""
    raw = (
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or Path.home() / ".claude"
    )
    return _validate_base(Path(raw))


def harness_root() -> Path:
    """Shipped-content base dir: CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > ~/.claude."""
    raw = (
        os.environ.get("CLAUDE_PLUGIN_ROOT")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or Path.home() / ".claude"
    )
    return _validate_base(Path(raw))
