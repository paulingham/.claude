"""Canonical Python path resolver — mirrors harness-paths.sh contract.

Three-tier resolution (matches hooks/_lib/harness-paths.sh:13-14):
  harness_data(): CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > Path.home()/".claude"
  harness_root(): CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > Path.home()/".claude"

Used by all hooks/_lib/*.py callers that previously hardcoded Path.home()/".claude".
Skills processes must use the sibling resolver module (independent sys.path).
"""
import os
from pathlib import Path


def harness_data() -> Path:
    """Runtime-state base dir: CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > ~/.claude."""
    return Path(
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or Path.home() / ".claude"
    )


def harness_root() -> Path:
    """Shipped-content base dir: CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > ~/.claude."""
    return Path(
        os.environ.get("CLAUDE_PLUGIN_ROOT")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or Path.home() / ".claude"
    )
