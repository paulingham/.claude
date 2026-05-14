"""YAML-aware loader for the `min_confidence:` field of an agent file.

Returns float when frontmatter sets `min_confidence` to a numeric value in
`[0.0, 1.0]`. Returns None silently for any other case: absent field,
non-numeric value, out-of-range, agent file does not exist. Never raises.
Mirrors the silent-None behaviour of agent_instinct_categories_loader.
"""
from agent_frontmatter_io import read_frontmatter, resolve_path


def _coerce(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0.0 <= float(value) <= 1.0 else None


def load_min_confidence(subagent_type):
    path = resolve_path(subagent_type)
    if not path:
        return None
    return _coerce(read_frontmatter(path).get("min_confidence"))
