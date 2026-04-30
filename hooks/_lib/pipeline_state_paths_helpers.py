"""Slice A — discovery globs + identity helpers for pipeline_state_paths."""
from pathlib import Path
from typing import Optional

WORKSTREAMS = "workstreams"
EXCLUDED_ROOT_DIRS = {WORKSTREAMS, "health-reports"}


def ws_root(state_dir: Path, workstream: Optional[str]) -> Path:
    return state_dir / WORKSTREAMS / workstream if workstream else state_dir


def _ws_glob(state_dir: Path, pattern: str) -> list:
    ws_dir = state_dir / WORKSTREAMS
    return list(ws_dir.glob(pattern)) if ws_dir.is_dir() else []


def legacy_paths(state_dir: Path) -> list:
    return list(state_dir.glob("*-pipeline.md")) + _ws_glob(state_dir, "*/*-pipeline.md")


def new_paths(state_dir: Path) -> list:
    root = [p for p in state_dir.glob("*/pipeline.md") if p.parent.name not in EXCLUDED_ROOT_DIRS]
    return root + _ws_glob(state_dir, "*/*/pipeline.md")


def task_id_of(path: Path) -> str:
    return path.parent.name if path.name == "pipeline.md" else path.name[:-len("-pipeline.md")]


def is_workstream(path: Path, state_dir: Path) -> bool:
    return (state_dir / WORKSTREAMS) in path.parents
