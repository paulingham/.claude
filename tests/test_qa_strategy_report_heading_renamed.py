"""AC5.8 — Report-format heading renamed to `### Property-Based Coverage Report`.

Asserts qa-test-strategy SKILL.md contains exactly one occurrence of
the renamed heading `### Property-Based Coverage Report`, AND zero
occurrences of the standalone procedural heading
`### Property-Based Coverage` (procedural one was deleted in AC5.2,
report one was renamed in AC5.8).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "qa-test-strategy" / "SKILL.md"


def test_report_format_heading_renamed_to_disambiguate():
    body = SKILL_PATH.read_text()
    # The renamed report-format heading must exist exactly once.
    renamed_count = len(re.findall(
        r"^###\s+Property-Based Coverage Report\s*$", body, re.MULTILINE))
    assert renamed_count == 1, (
        f"qa-test-strategy SKILL.md must contain exactly ONE "
        f"`### Property-Based Coverage Report` heading; got {renamed_count}")
    # The standalone procedural heading must be gone.
    standalone_count = len(re.findall(
        r"^###\s+Property-Based Coverage\s*$", body, re.MULTILINE))
    assert standalone_count == 0, (
        f"qa-test-strategy SKILL.md must NOT contain a standalone "
        f"`### Property-Based Coverage` heading after Slice 5; "
        f"got {standalone_count} occurrences")
