"""Python tag extractor — stdlib AST, no native dep.

Used for `.py` files unconditionally; the tree-sitter path is reserved
for the four other supported languages where stdlib lacks a parser.
Returns (def, ref) Tag instances:

- def: function / class / async-function definition sites
- ref: Name nodes with a Load context (variable / function reads)
"""
from __future__ import annotations

import ast
from pathlib import Path

from codebase_map.tags_types import Tag


def extract_python_tags(path: Path) -> list[Tag]:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    visitor = _PythonTagVisitor(str(path), path.stat().st_mtime)
    visitor.visit(tree)
    return visitor.tags


class _PythonTagVisitor(ast.NodeVisitor):
    """Collect (def, ref) tags from a Python AST."""

    def __init__(self, file: str, mtime: float):
        self.file = file
        self.mtime = mtime
        self.tags: list[Tag] = []

    def visit_FunctionDef(self, node):
        self._add("def", node.name, node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._add("def", node.name, node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._add("def", node.name, node)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self._add("ref", node.id, node)

    def _add(self, kind: str, name: str, node: ast.AST) -> None:
        self.tags.append(
            Tag(
                file=self.file,
                mtime=self.mtime,
                kind=kind,
                name=name,
                line=getattr(node, "lineno", 1),
                col=getattr(node, "col_offset", 0),
                lang="python",
            )
        )
