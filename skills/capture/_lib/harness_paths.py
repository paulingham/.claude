"""Sibling path resolver for skills/capture — verbatim copy of hooks/_lib/harness_paths.py.

Skills processes have an independent sys.path; cross-tree import from hooks/_lib is
fragile (M-a). This module is a local copy of the two resolver functions.
Do NOT import from hooks._lib.harness_paths here.

Three-tier resolution (matches hooks/_lib/harness-paths.sh:13-14):
  harness_data(): CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > Path.home()/".claude"
  harness_root(): CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > Path.home()/".claude"
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
