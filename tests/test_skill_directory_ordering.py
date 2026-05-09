"""AC3.4 — `/property-based-test` row sits immediately after `/tool-synthesis`.

Parses the Skill Directory table and asserts the row index of
`/property-based-test` is exactly index(`/tool-synthesis`) + 1. Both are
Build-phase utility skills invoked from `/build-implementation`;
co-locating them clusters Build-phase utilities for reader ergonomics.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _skill_table_rows(body):
    """Return ordered list of skill names from the first Skill Directory table."""
    # Find the first occurrence of the `### Skill Directory` heading section.
    section_match = re.search(
        r"### Skill Directory\n(.*?)(?=\n#### Deferred|\n### )",
        body, re.DOTALL)
    assert section_match, "Could not locate Skill Directory table"
    section = section_match.group(1)
    # Match table rows like `| `/skill-name` | ... | ... |`
    row_re = re.compile(r"^\|\s*`(/[a-z0-9-]+)`\s*\|", re.MULTILINE)
    return [m.group(1) for m in row_re.finditer(section)]


def test_pbt_row_immediately_after_tool_synthesis():
    body = CLAUDE_MD.read_text()
    names = _skill_table_rows(body)
    assert "/tool-synthesis" in names, (
        "Skill Directory missing /tool-synthesis (precondition)")
    assert "/property-based-test" in names, (
        "Skill Directory missing /property-based-test")
    tool_idx = names.index("/tool-synthesis")
    pbt_idx = names.index("/property-based-test")
    assert pbt_idx == tool_idx + 1, (
        f"/property-based-test must sit immediately after /tool-synthesis "
        f"(tool-synthesis index {tool_idx}, "
        f"property-based-test index {pbt_idx})")
