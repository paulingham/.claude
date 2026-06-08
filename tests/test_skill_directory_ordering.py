"""AC3.4 — `/harness:property-based-test` sits immediately after
`/harness:tool-synthesis`.

Parses the canonical Skill Directory catalog (protocols/skill-directory.md;
CLAUDE.md was pruned to a pointer — commit b606d59) and asserts the row index
of `/harness:property-based-test` is exactly index(`/harness:tool-synthesis`)
+ 1. Both are Build-phase utility skills invoked from
`/harness:build-implementation`; co-locating them clusters Build-phase
utilities for reader ergonomics.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRECTORY = REPO_ROOT / "protocols" / "skill-directory.md"


def _skill_table_rows(body):
    """Return ordered list of skill names from the Active Skills table."""
    # The catalog's main table lives under the `## Active Skills` heading.
    section_match = re.search(
        r"## Active Skills\n(.*?)(?=\n## )", body, re.DOTALL)
    assert section_match, "Could not locate Active Skills table"
    section = section_match.group(1)
    # Match table rows like `| `/harness:skill-name` | ... | ... |`
    row_re = re.compile(r"^\|\s*`(/[a-z0-9:-]+)`\s*\|", re.MULTILINE)
    return [m.group(1) for m in row_re.finditer(section)]


def test_pbt_row_immediately_after_tool_synthesis():
    body = SKILL_DIRECTORY.read_text()
    names = _skill_table_rows(body)
    assert "/harness:tool-synthesis" in names, (
        "Skill Directory missing /harness:tool-synthesis (precondition)")
    assert "/harness:property-based-test" in names, (
        "Skill Directory missing /harness:property-based-test")
    tool_idx = names.index("/harness:tool-synthesis")
    pbt_idx = names.index("/harness:property-based-test")
    assert pbt_idx == tool_idx + 1, (
        f"/harness:property-based-test must sit immediately after "
        f"/harness:tool-synthesis (tool-synthesis index {tool_idx}, "
        f"property-based-test index {pbt_idx})")
