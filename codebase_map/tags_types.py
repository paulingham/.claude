"""Shared type definitions — extracted into a leaf module so the
extractor sub-modules under codebase_map._lib can import without
creating an import cycle through codebase_map.tags.

Tag namedtuple shape is pinned by
`tests/contract/test_codebase_map_tag_contract.py`. Downstream slices
re-import Tag and depend on the field-order being stable.
"""
from __future__ import annotations

from collections import namedtuple

Tag = namedtuple("Tag", "file mtime kind name line col lang")


class CodebaseMapDependencyMissing(Exception):
    """Raised when a required native dep (tree_sitter_languages) is absent."""
