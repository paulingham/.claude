# KNOWN FALSE-NEGATIVE: static import/from-import only; importlib.spec_from_file_location
# dynamic loads + hyphenated-stem cycles are NOT detected.
from __future__ import annotations

import ast
from pathlib import Path


def _module_stems(lib_dir: str) -> set[str]:
    return {p.stem for p in Path(lib_dir).glob("*.py")}


def _edge_from_import(node: ast.Import, stems: set[str]) -> list[str]:
    return [alias.name.split(".")[0] for alias in node.names
            if alias.name.split(".")[0] in stems]


def _edge_from_import_from(node: ast.ImportFrom, stems: set[str]) -> list[str]:
    if node.level != 0 or not node.module:
        return []
    first = node.module.split(".")[0]
    return [first] if first in stems else []


def _edges_from_node(node: ast.AST, stems: set[str]) -> list[str]:
    if isinstance(node, ast.Import):
        return _edge_from_import(node, stems)
    if isinstance(node, ast.ImportFrom):
        return _edge_from_import_from(node, stems)
    return []


def _edges_from_tree(tree: ast.AST, stems: set[str]) -> list[str]:
    return [e for node in ast.walk(tree) for e in _edges_from_node(node, stems)]


def _imports_of(path: Path, stems: set[str]) -> list[str]:
    try:
        return _edges_from_tree(ast.parse(path.read_text()), stems)
    except Exception:
        return []


def _build_graph(lib_dir: str) -> dict[str, list[str]]:
    stems = _module_stems(lib_dir)
    graph: dict[str, list[str]] = {s: [] for s in stems}
    for path in Path(lib_dir).glob("*.py"):
        if path.stem in stems:
            graph[path.stem] = _imports_of(path, stems)
    return graph


def _record_back_edge(
    path: list[str], nxt: str, cycles: list[list[str]]
) -> None:
    cycles.append(path[path.index(nxt):] + [nxt])


def _push_node(
    color: dict[str, str], nxt: str, stack: list[str], path: list[str]
) -> None:
    color[nxt] = "GRAY"
    stack.append(nxt)
    path.append(nxt)


def _step_neighbor(
    color: dict[str, str],
    nxt: str,
    stack: list[str],
    path: list[str],
    cycles: list[list[str]],
    visited_edges: set[tuple[str, str]],
) -> None:
    edge = (stack[-1], nxt)
    if edge in visited_edges:
        return
    visited_edges.add(edge)
    if color[nxt] == "GRAY":
        _record_back_edge(path, nxt, cycles)
    elif color[nxt] == "WHITE":
        _push_node(color, nxt, stack, path)


def _next_unvisited(
    node: str,
    graph: dict[str, list[str]],
    color: dict[str, str],
    visited_edges: set[tuple[str, str]],
) -> str | None:
    return next(
        (n for n in graph.get(node, [])
         if n in color and (node, n) not in visited_edges),
        None,
    )


def _pop_node(
    node: str, color: dict[str, str], stack: list[str], path: list[str]
) -> None:
    stack.pop()
    if path and path[-1] == node:
        path.pop()
    color[node] = "BLACK"


def _advance_node(
    node: str,
    graph: dict[str, list[str]],
    color: dict[str, str],
    stack: list[str],
    path: list[str],
    cycles: list[list[str]],
    visited_edges: set[tuple[str, str]],
) -> None:
    nxt = _next_unvisited(node, graph, color, visited_edges)
    if nxt is not None:
        _step_neighbor(color, nxt, stack, path, cycles, visited_edges)
    else:
        _pop_node(node, color, stack, path)


def _dfs_from(
    start: str,
    graph: dict[str, list[str]],
    color: dict[str, str],
    visited_edges: set[tuple[str, str]],
) -> list[list[str]]:
    color[start] = "GRAY"
    stack, path, cycles = [start], [start], []
    while stack:
        _advance_node(stack[-1], graph, color, stack, path, cycles, visited_edges)
    return cycles


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    color = {n: "WHITE" for n in graph}
    visited_edges: set[tuple[str, str]] = set()
    return [c for start in graph if color[start] == "WHITE"
            for c in _dfs_from(start, graph, color, visited_edges)]


def detect_cycles(lib_dir: str) -> list[list[str]]:
    return _find_cycles(_build_graph(lib_dir))
