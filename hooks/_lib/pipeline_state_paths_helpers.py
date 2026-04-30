"""Slice A — discovery globs + identity helpers for pipeline_state_paths."""
from pathlib import Path
from typing import Optional


def ws_root(state_dir: Path, workstream: Optional[str]) -> Path:
    return state_dir / "workstreams" / workstream if workstream else state_dir


def legacy_paths(state_dir: Path) -> list:
    ws_dir = state_dir / "workstreams"
    nested = list(ws_dir.glob("*/*-pipeline.md")) if ws_dir.is_dir() else []
    return list(state_dir.glob("*-pipeline.md")) + nested


def new_paths(state_dir: Path) -> list:
    excluded = {"workstreams", "health-reports"}
    root = [p for p in state_dir.glob("*/pipeline.md") if p.parent.name not in excluded]
    ws_dir = state_dir / "workstreams"
    nested = list(ws_dir.glob("*/*/pipeline.md")) if ws_dir.is_dir() else []
    return root + nested


def task_id_of(path: Path) -> str:
    return path.parent.name if path.name == "pipeline.md" else path.name[:-len("-pipeline.md")]


def is_workstream(path: Path, state_dir: Path) -> bool:
    return (state_dir / "workstreams") in path.parents
