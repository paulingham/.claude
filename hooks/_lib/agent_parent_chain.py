"""Transitive parent-chain resolver for agent instinct inheritance (C6.2).

resolve_parent_chain walks frontmatter `parent:` until absent or cycle.
load_expanded_instinct_categories returns own + ancestor flat categories.
Missing parent file → stderr + JSONL warning (visited but not raised).
Cycle protection via visited-set.
"""
from agent_frontmatter_io import read_frontmatter, resolve_path
from agent_instinct_categories_loader import load_agent_instinct_categories
from agent_parent_chain_warn import warn_missing_parent


def _next_parent(name, visited):
    path = resolve_path(name)
    if not path:
        return None
    parent = read_frontmatter(path).get("parent")
    return parent if parent and parent not in visited else None


def resolve_parent_chain(subagent_type):
    chain, visited, current = [], {subagent_type}, subagent_type
    while True:
        parent = _next_parent(current, visited)
        if not parent:
            return chain
        if not resolve_path(parent):
            warn_missing_parent(current, parent)
            return chain
        chain.append(parent)
        visited.add(parent)
        current = parent


def load_expanded_instinct_categories(subagent_type):
    roles = [subagent_type, *resolve_parent_chain(subagent_type)]
    expanded = set()
    for role in roles:
        expanded.update(load_agent_instinct_categories(role) or [])
    return sorted(expanded)
