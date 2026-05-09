"""AC2.2 — `pbt-engineer` tools allowlist is exact.

Asserts `tools` is exactly `{Read, Write, Edit, Bash, Grep, Glob}` and
`Agent`/`Skill` are absent and explicitly listed in `disallowedTools`.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"

EXPECTED_TOOLS = {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}


def _parse_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1))


def test_pbt_engineer_tools_allowlist_exact():
    fm = _parse_frontmatter(AGENT_PATH)
    actual_tools = set(fm.get("tools") or [])
    assert actual_tools == EXPECTED_TOOLS, (
        f"pbt-engineer tools drift: expected {EXPECTED_TOOLS}, "
        f"got {actual_tools}")
    assert "Agent" not in actual_tools, "pbt-engineer must not grant Agent"
    assert "Skill" not in actual_tools, "pbt-engineer must not grant Skill"
    disallowed = set(fm.get("disallowedTools") or [])
    assert {"Agent", "Skill"}.issubset(disallowed), (
        f"pbt-engineer disallowedTools must include both Agent and Skill, "
        f"got {disallowed}")
