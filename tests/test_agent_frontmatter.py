"""Every agent file must declare both `executor:` and `advisor:` fields.

Locks in the executor/advisor frontmatter contract introduced for the
Sonnet-executor + Opus-advisor pairing pattern. `advisor: none` (a string)
is acceptable when an advisor is intentionally not configured.
"""
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
EXCLUDED_SUBDIRS = {"dynamic", "archive"}


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _discover_agent_files() -> list:
    files = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if any(part in EXCLUDED_SUBDIRS for part in path.relative_to(AGENTS_DIR).parts):
            continue
        files.append(path)
    return files


def _is_valid_executor(value) -> bool:
    return isinstance(value, str) and value.startswith("claude-")


def _is_valid_advisor(value) -> bool:
    if value == "none":
        return True
    return isinstance(value, str) and value.startswith("claude-")


class EveryAgentDeclaresExecutorAndAdvisor(unittest.TestCase):
    def test_executor_present_and_valid(self):
        for path in _discover_agent_files():
            fm = _parse_frontmatter(path)
            value = fm.get("executor")
            self.assertTrue(
                _is_valid_executor(value),
                f"{path.name}: 'executor' missing or invalid (got {value!r}); "
                f"expected a string starting with 'claude-'",
            )

    def test_advisor_present_and_valid(self):
        for path in _discover_agent_files():
            fm = _parse_frontmatter(path)
            self.assertIn(
                "advisor", fm,
                f"{path.name}: 'advisor' field missing from frontmatter",
            )
            value = fm["advisor"]
            self.assertTrue(
                _is_valid_advisor(value),
                f"{path.name}: 'advisor' invalid (got {value!r}); "
                f"expected 'none' or a string starting with 'claude-'",
            )


if __name__ == "__main__":
    unittest.main()
