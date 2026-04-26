"""Safely load an agent's frontmatter by subagent_type.

Validates `subagent_type` against an allowlist regex AND asserts the resolved
path stays inside `_AGENTS_DIR`. Either check failing returns `{}` (which the
caller treats identically to 'agent file not found' — falls through to the
solo `no-pairing-frontmatter` path).
"""
import os
import re
from pathlib import Path

from advisor_resolver import parse_frontmatter

_AGENTS_DIR = Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                   Path.home() / ".claude" / "agents")
_VALID_SUBAGENT = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def _is_contained(path):
    return path.is_relative_to(_AGENTS_DIR.resolve()) and path.exists()


def load_agent_frontmatter(subagent_type):
    if not subagent_type or not _VALID_SUBAGENT.match(subagent_type):
        return {}
    path = (_AGENTS_DIR / f"{subagent_type}.md").resolve()
    return parse_frontmatter(path.read_text()) if _is_contained(path) else {}
