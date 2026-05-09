"""AC3.3 — CLAUDE.md Skill Directory has the /property-based-test row.

Asserts the Skill Directory table contains a row for `/property-based-test`
with all three verdicts named in the Verdict column.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def test_skill_directory_has_pbt_row():
    body = CLAUDE_MD.read_text()
    # Find a row that starts with `/property-based-test` (in backticks).
    pattern = re.compile(
        r"^\|\s*`/property-based-test`\s*\|.*$", re.MULTILINE)
    m = pattern.search(body)
    assert m, "CLAUDE.md Skill Directory missing /property-based-test row"
    row_text = m.group(0)
    for verdict in ("PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED"):
        assert verdict in row_text, (
            f"/property-based-test row missing verdict {verdict!r}: "
            f"{row_text}")
