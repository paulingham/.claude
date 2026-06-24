"""AC2.1 — `pbt-engineer` agent has required frontmatter keys.

Asserts every required key is present, `tools` is a YAML list (not
comma-string), `instinct_categories` is a YAML list, and `executor`
resolves to a known Claude model id.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"

REQUIRED_KEYS = (
    "name", "description", "tools", "model",
    "executor", "advisor", "instinct_categories", "disallowedTools",
)
KNOWN_EXECUTORS = (
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5",
    "mid",
    "strong",
    "cheap",
)


def _parse_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1))


def test_pbt_engineer_has_required_frontmatter_keys():
    fm = _parse_frontmatter(AGENT_PATH)
    missing = [k for k in REQUIRED_KEYS if k not in fm]
    assert not missing, f"pbt-engineer frontmatter missing keys: {missing!r}"
    assert fm["name"] == "pbt-engineer", (
        f"name must be 'pbt-engineer', got {fm['name']!r}")
    assert isinstance(fm["tools"], list), (
        f"tools must be a YAML list, got {type(fm['tools']).__name__}")
    assert isinstance(fm["instinct_categories"], list), (
        f"instinct_categories must be a YAML list, "
        f"got {type(fm['instinct_categories']).__name__}")
    assert fm["executor"] in KNOWN_EXECUTORS, (
        f"executor must resolve to a known model id, got {fm['executor']!r}")
