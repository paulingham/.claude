"""Sibling path resolver for skills/reindex-memory — verbatim copy of hooks/_lib/harness_paths.py.

Skills processes have an independent sys.path; cross-tree import from hooks/_lib is
fragile (M-a). This module is a local copy of the two resolver functions.
Do NOT import from hooks._lib.harness_paths here.

Three-tier resolution (matches hooks/_lib/harness-paths.sh:13-14):
  harness_data(): CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > Path.home()/".claude"
  harness_root(): CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > Path.home()/".claude"
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
