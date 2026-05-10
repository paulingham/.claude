"""Public surface for the codebase_map.tags slice.

Pinned by `tests/contract/test_codebase_map_tag_contract.py`.

The heavy lifting lives in `codebase_map._lib.{walk,python_ast,
treesitter,cache}`. This module is intentionally thin: it composes the
helpers, exposes the public callables (`Tag`, `extract_tags`,
`walk_repo`, `cached_tags`, `CodebaseMapDependencyMissing`), and
provides the `_get_parser` seam that the AC7 mock targets.

Implementation choice (decision, see scratchpad): Python files are
tagged via stdlib `ast`; the four other languages flow through the
plan-named `tree_sitter_languages` import. AC7's typed exception
covers the dep-missing case for the four non-Python languages.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

from codebase_map._lib import cache as _cache
from codebase_map._lib.python_ast import extract_python_tags
from codebase_map._lib.treesitter import extract_treesitter_tags
from codebase_map._lib.walk import walk_repo  # noqa: F401 — re-exported
from codebase_map.tags_types import CodebaseMapDependencyMissing, Tag

__all__ = (
    "CodebaseMapDependencyMissing",
    "Tag",
    "cached_tags",
    "extract_tags",
    "walk_repo",
)


_LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rb": "ruby",
    ".go": "go",
}

_DEFAULT_LANG_ALLOWLIST = "python,typescript,javascript,ruby,go"


def extract_tags(path: Path | str) -> list[Tag]:
    """Extract def/ref tags for a single file.

    Returns [] when the file's language is outside the allowlist.
    Raises CodebaseMapDependencyMissing when a non-Python language is
    requested but the native tree-sitter dep cannot be loaded.
    """
    path = Path(path)
    lang = _LANG_BY_EXT.get(path.suffix.lower())
    if lang is None or not _language_allowed(lang):
        return []
    if lang == "python":
        return extract_python_tags(path)
    parser = _safely_get_parser(lang)
    return extract_treesitter_tags(path, lang, parser)


def cached_tags(db_path: Path, files: Iterable[Path | str]) -> list[Tag]:
    """Cache-aware bulk extractor.

    Looks up `extract_tags` from the current module at call time so
    that test doubles (`mock.patch.object(tags_mod, "extract_tags",
    ...)`) are observable through the cache layer (AC4 contract).
    """
    me = sys.modules[__name__]
    return _cache.cached_tags(db_path, files, me.extract_tags)


def _language_allowed(lang: str) -> bool:
    raw = os.environ.get("CLAUDE_CODEBASE_MAP_LANGUAGES",
                         _DEFAULT_LANG_ALLOWLIST)
    allowed = {p.strip() for p in raw.split(",") if p.strip()}
    return lang in allowed


def _safely_get_parser(lang: str):
    try:
        return _get_parser(lang)
    except ImportError as exc:
        raise CodebaseMapDependencyMissing(
            "codebase-map: missing tree_sitter_languages — "
            "run `pip install tree-sitter-languages` to enable "
            f"{lang} extraction"
        ) from exc


def _get_parser(lang: str):
    """Return a tree-sitter Parser for the named language.

    Mocked by the AC7 test to simulate ImportError. When the native
    lib is absent OR the requested language grammar cannot be loaded,
    this function MUST raise ImportError so the caller can wrap into
    CodebaseMapDependencyMissing.
    """
    from tree_sitter_languages import get_parser
    return get_parser(lang)
