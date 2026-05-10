"""Tree-sitter tag extractor for the four non-Python languages.

Activated only by `extract_tags` when the file is TS / JS / Ruby / Go
AND the parser load succeeded. Slice C will isolate this path in a
subprocess so a SIGSEGV in the native grammar cannot poison the hook.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from codebase_map.tags_types import Tag

_DEF_TYPES = frozenset({
    "function_declaration",
    "function_definition",
    "method_definition",
    "class_declaration",
    "class_definition",
})

_REF_TYPES = frozenset({
    "identifier",
    "type_identifier",
})


def extract_treesitter_tags(path: Path, lang: str, parser) -> list[Tag]:
    src = path.read_bytes()
    tree = parser.parse(src)
    mtime = path.stat().st_mtime
    return list(_walk_node(tree.root_node, str(path), mtime, lang))


def _walk_node(node, file: str, mtime: float, lang: str) -> Iterator[Tag]:
    tag = _node_to_tag(node, file, mtime, lang)
    if tag is not None:
        yield tag
    for child in node.children:
        yield from _walk_node(child, file, mtime, lang)


def _node_to_tag(node, file: str, mtime: float, lang: str) -> Tag | None:
    kind = _classify_node(node)
    if kind is None:
        return None
    name = _node_name(node)
    if not name:
        return None
    return Tag(
        file=file,
        mtime=mtime,
        kind=kind,
        name=name,
        line=node.start_point[0] + 1,
        col=node.start_point[1],
        lang=lang,
    )


def _classify_node(node) -> str | None:
    if node.type in _DEF_TYPES:
        return "def"
    if node.type in _REF_TYPES:
        return "ref"
    return None


def _node_name(node) -> str | None:
    if node.type in _DEF_TYPES:
        named = node.child_by_field_name("name")
        if named is not None:
            return named.text.decode("utf-8", errors="replace")
        return None
    return node.text.decode("utf-8", errors="replace")
