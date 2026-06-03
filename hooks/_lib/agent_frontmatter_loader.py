"""Safely load an agent's frontmatter by subagent_type.

Validates `subagent_type` against an allowlist regex AND asserts the resolved
path stays inside `_AGENTS_DIR`. Either check failing returns `{}` (which the
caller treats identically to 'agent file not found' — falls through to the
solo `no-pairing-frontmatter` path).

Agent frontmatter is full YAML (may contain nested blocks such as
`model_conditional`). We use `yaml.safe_load` on the frontmatter block so
nested structures are preserved. The pipeline-state `parse_frontmatter` is a
flat key-value parser suited for pipeline state files; it is NOT used here.
"""
import os
import re
from pathlib import Path

_AGENTS_DIR = Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                   Path.home() / ".claude" / "agents")
_VALID_SUBAGENT = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _is_contained(path):
    return path.is_relative_to(_AGENTS_DIR.resolve()) and path.exists()


def _parse_yaml_frontmatter(text):
    """Parse YAML frontmatter block from a Markdown file."""
    try:
        import yaml
        match = _FRONTMATTER_RE.match(text)
        return yaml.safe_load(match.group(1)) or {} if match else {}
    except Exception:
        return {}


def load_agent_frontmatter(subagent_type):
    if not subagent_type or not _VALID_SUBAGENT.match(subagent_type):
        return {}
    path = (_AGENTS_DIR / f"{subagent_type}.md").resolve()
    return _parse_yaml_frontmatter(path.read_text()) if _is_contained(path) else {}
