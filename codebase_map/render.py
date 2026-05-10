"""Token-budgeted markdown render for the codebase-map digest.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice B (AC11, AC13).

Token-counting proxy
====================

There is no harness precedent for ``tiktoken`` or any other tokeniser
package, and the architect's plan explicitly chose **chars-per-token at
~4** as the proxy — the same heuristic Aider's repomap uses internally.
``count_tokens(s) = ceil(len(s) / 4)`` is the entire model. Calls into
``count_tokens`` MUST NOT mention ``project-hash`` (this is private
state, never part of user-facing output — covered by Slice F AC34
negative assertion).

Truncation order (AC11)
=======================

When the rendered digest would exceed ``budget`` tokens, lowest-ranked
symbols are dropped first. The render walks files in score-descending
order and stops adding bullets when the cumulative token count would
exceed the budget. The empty-state path (AC13) returns a one-line
marker ``codebase-map: empty (no supported source files)``.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import networkx as nx

_CHARS_PER_TOKEN = 4

_EMPTY_STATE_MARKER = "codebase-map: empty (no supported source files)\n"


def count_tokens(text: str) -> int:
    """Approximate token count using a 4-chars-per-token proxy.

    The proxy is intentionally simple — no tokeniser dependency, no
    embedding lookups, byte-deterministic across Python versions. Aider
    uses the same heuristic when no tokeniser is available.
    """
    if not text:
        return 0
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


def render(
    graph: nx.DiGraph,
    scores: Mapping[str, float],
    budget: int = 1024,
) -> str:
    """Render a token-budget-constrained markdown digest.

    Files are listed in descending PageRank score; lowest-ranked
    files are truncated first when the budget is exceeded. An empty
    graph returns the documented one-line empty-state marker (AC13).
    """
    if graph.number_of_nodes() == 0 or not scores:
        return _EMPTY_STATE_MARKER

    header = "# Codebase Map\n\n"
    header_tokens = count_tokens(header)
    body_lines: list[str] = []
    used_tokens = header_tokens

    for file in _files_by_score_desc(scores):
        line = _render_file_line(file, scores[file])
        line_tokens = count_tokens(line)
        if used_tokens + line_tokens > budget:
            break
        body_lines.append(line)
        used_tokens += line_tokens

    if not body_lines:
        return _EMPTY_STATE_MARKER
    return header + "".join(body_lines)


def _files_by_score_desc(scores: Mapping[str, float]) -> list[str]:
    """Return files in descending score order; ties broken alphabetically.

    The secondary alphabetical tiebreaker keeps output byte-stable when
    PageRank produces equal scores (degenerate graphs).
    """
    return sorted(scores, key=lambda f: (-scores[f], f))


def _render_file_line(file: str, score: float) -> str:
    return f"- {file} ({score:.4f})\n"
