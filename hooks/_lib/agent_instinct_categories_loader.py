"""YAML-aware loader for the `instinct_categories:` field of an agent file.

Returns a list of strings when the field is a YAML list, None otherwise.
File-I/O helpers live in `agent_frontmatter_io` (shared with the
parent-chain resolver — see `agent_parent_chain`).
"""
from agent_frontmatter_io import read_frontmatter, resolve_path


def load_agent_instinct_categories(subagent_type):
    path = resolve_path(subagent_type)
    cats = read_frontmatter(path).get("instinct_categories") if path else None
    return cats if isinstance(cats, list) else None
