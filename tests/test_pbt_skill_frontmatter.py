"""AC1.1 — `/property-based-test` skill frontmatter.

Asserts the new SKILL.md is parseable by the harness skill loader
contract: YAML frontmatter present, `name == "property-based-test"`,
`agent == "pbt-engineer"`, `description` non-empty.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"


def _parse_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1))


def test_property_based_test_skill_has_required_frontmatter():
    fm = _parse_frontmatter(SKILL_PATH)
    assert fm.get("name") == "property-based-test", (
        f"frontmatter `name` must be 'property-based-test', got {fm.get('name')!r}")
    assert fm.get("agent") == "pbt-engineer", (
        f"frontmatter `agent` must be 'pbt-engineer', got {fm.get('agent')!r}")
    description = fm.get("description")
    assert isinstance(description, str) and description.strip(), (
        "frontmatter `description` must be a non-empty string")
