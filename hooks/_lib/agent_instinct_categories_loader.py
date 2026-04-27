"""YAML-aware loader for the `instinct_categories:` field of an agent file.

Returns a list of strings when the field is a YAML list, None otherwise.
Refuses traversal subagent_type strings via `agent_path_validator`.

Mirrors `agent_tools_loader.py` to keep the broken pipeline_frontmatter
parser quarantined — uses `yaml.safe_load` directly.
"""
import os
import re
from pathlib import Path

import yaml

from agent_path_validator import is_valid_subagent_type


def _agents_dir():
    return Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                Path.home() / ".claude" / "agents")


def _read_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


def _resolve_path(subagent_type):
    if not is_valid_subagent_type(subagent_type):
        return None
    path = (_agents_dir() / f"{subagent_type}.md").resolve()
    return path if path.exists() else None


def load_agent_instinct_categories(subagent_type):
    path = _resolve_path(subagent_type)
    cats = _read_frontmatter(path).get("instinct_categories") if path else None
    return cats if isinstance(cats, list) else None
