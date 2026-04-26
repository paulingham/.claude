"""YAML-aware loader for the `tools:` field of an agent frontmatter file.

Returns a list of strings when `tools:` is a YAML list, None otherwise.
"""
import os
import re
from pathlib import Path

import yaml


def _agents_dir():
    return Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                Path.home() / ".claude" / "agents")


def _read_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


def load_agent_tools(subagent_type):
    path = (_agents_dir() / f"{subagent_type}.md").resolve()
    fm = _read_frontmatter(path)
    tools = fm.get("tools")
    return tools if isinstance(tools, list) else None
