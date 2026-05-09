"""AC5.4 — Test Coverage Report Format `### Property-Based Coverage Report` table preserved.

Asserts the report table (header row
`| Function | Path | Properties | Outcome | Counterexamples Frozen |`
and summary bullets including `- **Functions covered**: N`) is present
byte-for-byte after Slice 5 lands. Heading text is renamed (per AC5.8)
but the table content body is preserved unchanged.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "qa-test-strategy" / "SKILL.md"

TABLE_HEADER_ROW = (
    "| Function | Path | Properties | Outcome | Counterexamples Frozen |")
SUMMARY_BULLET = "- **Functions covered**: N"


def test_pbt_report_table_preserved_byte_for_byte():
    body = SKILL_PATH.read_text()
    assert TABLE_HEADER_ROW in body, (
        f"Report-format table header row must be preserved byte-for-byte: "
        f"{TABLE_HEADER_ROW!r}")
    assert SUMMARY_BULLET in body, (
        f"Report-format summary bullet must be preserved byte-for-byte: "
        f"{SUMMARY_BULLET!r}")
