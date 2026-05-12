"""Spec-blind validator fixtures.

Locates the repo root by walking up until ``settings.json`` is found, so the
suite remains agnostic to the actual worktree path.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "settings.json").is_file() and (parent / "rules").is_dir():
            return parent
    raise RuntimeError(
        "spec-blind: could not discover repo root (no settings.json + rules dir on path)"
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _find_repo_root()


@pytest.fixture(scope="session")
def settings_json_path(repo_root: Path) -> Path:
    return repo_root / "settings.json"


@pytest.fixture(scope="session")
def instinct_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "learning"
        / "8efffd88329f34786e1828737702e911"
        / "instincts"
        / "v2.1.139-native-surface-mismatch.md"
    )
