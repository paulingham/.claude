"""Path resolution helpers for the analyser CLI."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_paths import harness_data

from tiering import default_project_hash


def _home() -> Path:
    return harness_data()


def obs_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "observations.jsonl"


def costs_path(arg: str | None) -> Path:
    return Path(arg) if arg else _home() / "metrics" / "costs.jsonl"


def out_path(arg: str | None, phash: str) -> Path:
    return Path(arg) if arg else _home() / "learning" / phash / "model-recommendations.md"


def resolve_phash(arg: str | None) -> str:
    return arg or default_project_hash()
