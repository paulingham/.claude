"""Repo walker with default-or'd exclusion regex.

AC2-bis: defaults are non-removable. The optional `exclude_dirs` arg
and the `CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS` env var ADD additional
patterns; they never replace the defaults. A hostile or empty env
override therefore cannot re-include `.git/`, `node_modules/`, or
worktree siblings.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

_DEFAULT_EXCLUDE_PATTERNS = (
    r"^agent-",
    r"^\.git$",
    r"^node_modules$",
    r"^dist$",
    r"^build$",
    r"^worktrees$",
)


def walk_repo(
    root: Path,
    exclude_dirs: Iterable[str] | None = None,
) -> Iterator[Path]:
    """Yield repo files, excluding well-known noise directories."""
    pattern = _build_exclude_pattern(exclude_dirs)
    for current, subdirs, filenames in os.walk(root):
        subdirs[:] = [d for d in subdirs if not pattern.match(d)]
        for name in filenames:
            yield Path(current) / name


def _build_exclude_pattern(extra: Iterable[str] | None) -> re.Pattern[str]:
    sources = list(_DEFAULT_EXCLUDE_PATTERNS)
    sources.extend(_extra_patterns(extra))
    sources.extend(_env_extra_patterns())
    return re.compile("|".join(f"(?:{p})" for p in sources))


def _extra_patterns(extra: Iterable[str] | None) -> list[str]:
    if extra is None:
        return []
    return [p for p in extra if p]


def _env_extra_patterns() -> list[str]:
    raw = os.environ.get("CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS", "")
    return [p.strip() for p in raw.split(",") if p.strip()]
