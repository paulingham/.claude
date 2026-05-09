"""AC1.6 — `/property-based-test` skill cites arXiv 2510.09907.

Asserts the skill body references the source paper AND has a
`Reference` or `Rationale` heading.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"


def test_skill_cites_arxiv_2510_09907():
    body = SKILL_PATH.read_text()
    assert "2510.09907" in body, (
        "property-based-test SKILL.md must cite arXiv 2510.09907")
    has_reference_heading = bool(
        re.search(r"^#+\s+(Reference|Rationale)", body, re.MULTILINE | re.IGNORECASE))
    assert has_reference_heading, (
        "property-based-test SKILL.md must contain a `Reference` or "
        "`Rationale` heading")
