"""Path resolution helpers for the analyser CLI."""
from __future__ import annotations

import os
from pathlib import Path

from tiering import default_project_hash


def _home() -> Path:
    root = (
        os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or os.path.join(os.path.expanduser("~"), ".claude")
    )
    return Path(root)


def obs_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "observations.jsonl"


def costs_path(arg: str | None) -> Path:
    return Path(arg) if arg else _home() / "metrics" / "costs.jsonl"


def out_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "model-recommendations.md"


def resolve_phash(arg: str | None) -> str:
    return arg or default_project_hash()
