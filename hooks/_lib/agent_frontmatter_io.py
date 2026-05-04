"""Shared file-I/O helpers for agent frontmatter (extracted Wave 5/C6.2).

Used by both the flat instinct_categories loader and the parent-chain
resolver. Keeps both files within the 50-line shape ceiling.
"""
import os
import re
from pathlib import Path

import yaml

from agent_path_validator import is_valid_subagent_type


def agents_dir():
    return Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                Path.home() / ".claude" / "agents")


def read_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


def resolve_path(subagent_type):
    if not is_valid_subagent_type(subagent_type):
        return None
    path = (agents_dir() / f"{subagent_type}.md").resolve()
    return path if path.exists() else None
