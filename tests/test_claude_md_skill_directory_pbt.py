"""AC3.3 — Skill Directory has the /harness:property-based-test row.

CLAUDE.md was pruned to a pointer (commit b606d59); the canonical Skill
Directory catalog (with /harness:-prefixed rows) now lives in
protocols/skill-directory.md. Asserts the table contains a row for
`/harness:property-based-test` with all three verdicts named.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRECTORY = REPO_ROOT / "protocols" / "skill-directory.md"


def test_skill_directory_has_pbt_row():
    body = SKILL_DIRECTORY.read_text()
    # Find a row that starts with `/harness:property-based-test` (in backticks).
    pattern = re.compile(
        r"^\|\s*`/harness:property-based-test`\s*\|.*$", re.MULTILINE)
    m = pattern.search(body)
    assert m, ("protocols/skill-directory.md missing "
               "/harness:property-based-test row")
    row_text = m.group(0)
    for verdict in ("PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED"):
        assert verdict in row_text, (
            f"/harness:property-based-test row missing verdict {verdict!r}: "
            f"{row_text}")
