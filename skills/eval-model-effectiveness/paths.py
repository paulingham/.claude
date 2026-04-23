"""Path resolution helpers for the analyser CLI."""
from __future__ import annotations

import os
from pathlib import Path

from tiering import default_project_hash


def _home() -> Path:
    return Path(os.path.expanduser("~/.claude"))


def obs_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "observations.jsonl"


def costs_path(arg: str | None) -> Path:
    return Path(arg) if arg else _home() / "metrics" / "costs.jsonl"


def out_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "model-recommendations.md"


def resolve_phash(arg: str | None) -> str:
    return arg or default_project_hash()
